from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Case, DecimalField, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils.functional import SimpleLazyObject

from coldfront.core.allocation.models import Allocation
from coldfront.core.project.models import ProjectUser

from coldfront_billing.constants import (
    BILLING_ROLE_NAME,
    MANAGER_ROLE_NAME,
    NO_COST_QUOTA_TYPE_ATTR_NAME,
    QUOTA_ATTR_NAME,
)
from coldfront_billing.data import UNIT_TO_TB, BillingQuota
from coldfront_billing.enums import AllocationStatus, ProjectStatus, StorageUnit
from coldfront_billing.models.common import UNITS_CHOICES, QuotaBase

User = get_user_model()


class NoCostQuota(QuotaBase):
    """
    Represents a no-cost quota allocation for a specific user
    and a class of Resources identified by quota_type.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='no_cost_quotas',
        help_text='User who owns this no-cost quota',
    )

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'quota_type'], name='uniq_nocostquota_user_quota_type')]
        verbose_name = 'No Cost Quota'
        verbose_name_plural = 'No Cost Quotas'

    def clean(self):
        super().clean()

        allowed_units = dict(UNITS_CHOICES)
        if self.units not in allowed_units:
            raise ValidationError(
                {'units': f'Invalid units: {self.units}. Allowed: {", ".join(allowed_units.keys())}.'}
            )

        if self.amount_tb * Decimal(1000) < Decimal(self.increment_gb):
            raise ValidationError(
                {
                    'amount': f'Amount {self.amount_tb} TB cannot be smaller than allocation increment {self.increment_gb} GB.'
                }
            )

    def __str__(self):
        return f'{str(self.user)} - {self.quota_type}'


class NoCostQuotaAllotment(models.Model):
    no_cost_quota = models.ForeignKey(
        NoCostQuota,
        on_delete=models.CASCADE,
        related_name='allotments',
        help_text='No-cost quota this allotment draws from',
    )
    allocation = models.ForeignKey(
        Allocation,
        on_delete=models.CASCADE,
        related_name='no_cost_quota_allotments',
        help_text='Allocation for a resource with no-cost quota type',
    )

    amount_tb = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        help_text='Allotted quota amount',
        default=Decimal('0.000'),
        validators=[MinValueValidator(Decimal('0.000'))],
    )  # 3 decimal places to support GB precision (e.g., 0.001 TB = 1 GB)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['no_cost_quota', 'allocation'],
                name='uniq_nocostquotaallotment_quota_allocation',
            ),
            models.CheckConstraint(check=models.Q(amount_tb__gte=Decimal('0.000')), name='amount_tb_must_be_positive'),
        ]

    def clean(self):
        if self.no_cost_quota_id and self.allocation_id:
            user = self.no_cost_quota.user
            project = self.allocation.project

            is_pi = project.pi_id == user.id
            has_billing_role = ProjectUser.objects.filter(
                project=project,
                user=user,
                role__name__in=[BILLING_ROLE_NAME, MANAGER_ROLE_NAME],
                status__name=ProjectStatus.ACTIVE,
            ).exists()
            if not (is_pi or has_billing_role):
                raise ValidationError(
                    {
                        'no_cost_quota': "User must be project PI or have Manager or Billing role on the allocation's project."
                    }
                )

            quota_type = self.no_cost_quota.quota_type
            if not self.allocation.resources.filter(
                resourceattribute__resource_attribute_type__name=NO_COST_QUOTA_TYPE_ATTR_NAME,
                resourceattribute__value=quota_type,
            ).exists():
                raise ValidationError(
                    {'allocation': f"Allocation's resource does not have {NO_COST_QUOTA_TYPE_ATTR_NAME}='{quota_type}'"}
                )

            min_inc = Decimal(self.no_cost_quota.increment_gb)
            if self.amount_tb * Decimal(1000) < min_inc:
                raise ValidationError({'amount': 'Amount cannot be smaller than allocation increment.'})

            # Ensure the amount is a multiple of increment_gb
            if self.no_cost_quota.units == 'TB':
                min_inc = Decimal(self.no_cost_quota.increment_gb) / Decimal(1000)  # Convert GB to TB
            else:
                min_inc = Decimal(self.no_cost_quota.increment_gb)  # Already in GB
            minimum = f'{min_inc} {self.no_cost_quota.units}'
            if not self.amount_tb % min_inc == 0:
                raise ValidationError({'amount': f'Allotment amount must be a multiple of increment ({minimum})'})

            if self.no_cost_quota.units == 'TB':
                allotment_amount = self.amount_tb
            else:
                allotment_amount = self.amount_tb * Decimal(1000)  # Convert TB to GB for comparison
            amount = f'{allotment_amount} {self.no_cost_quota.units}'
            if self.amount_tb > (ncq_amount := self.no_cost_quota.amount_tb):
                if self.no_cost_quota.units == 'TB':
                    ncq_amount = self.no_cost_quota.amount_tb
                else:
                    ncq_amount = self.no_cost_quota.amount_tb * Decimal(1000)  # Convert TB to GB for comparison
                no_cost_quota = f'{ncq_amount} {self.no_cost_quota.units}'
                raise ValidationError(
                    {
                        'amount': f'No cost quota allotment size ({amount}) is bigger than no-cost quota size ({no_cost_quota})'
                    }
                )
            allocation_quota_value = self.allocation.get_attribute(QUOTA_ATTR_NAME)

            if not allocation_quota_value:
                return

            allocation_quota = BillingQuota.create(
                Decimal(allocation_quota_value).quantize(Decimal('0.01')), StorageUnit.TB
            )
            allotment_quota = BillingQuota.create(self.amount_tb, self.no_cost_quota.units)

            if (allotment_size := allotment_quota.amount_tb) > (alloc_size := allocation_quota.amount_tb):
                raise ValidationError(
                    {
                        'amount': f'No cost quota allotment size ({allotment_size}) is bigger than allocation size ({alloc_size} TB)'
                    }
                )

    def __str__(self):
        return f'Allotment from {self.no_cost_quota_id} on  {str(self.allocation_id)}'


def to_tb(expr):
    return Case(
        When(units='TB', then=expr),
        When(units='GB', then=expr * Value(UNIT_TO_TB[StorageUnit.GB])),
        default=expr,
        output_field=DecimalField(),
    )


def _build_quota_with_remaining():
    return NoCostQuota.objects.annotate(
        used=Coalesce(Sum('allotments__amount_tb'), Value(Decimal('0')), output_field=DecimalField()),
        used_inactive=Coalesce(
            Sum(
                'allotments__amount_tb',
                filter=~Q(allotments__allocation__status__name=AllocationStatus.ACTIVE),
            ),
            Value(Decimal('0')),
            output_field=DecimalField(),
        ),
    ).annotate(
        remaining=F('amount_tb') - F('used'),
        remaining_inactive=F('amount_tb') - F('used_inactive'),
        amount_normalized=to_tb(F('amount_tb')),
        remaining_normalized=to_tb(F('remaining')),
    )


# Built lazily: NoCostQuota.objects.annotate(...) touches Django's app registry
# (via get_fields()), which isn't ready yet while models are still being imported.
quota_with_remaining = SimpleLazyObject(_build_quota_with_remaining)
