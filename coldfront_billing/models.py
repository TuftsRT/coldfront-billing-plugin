from coldfront.core.allocation.models import Allocation
from coldfront.core.project.models import Project, ProjectUser
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models

from .constants import BILLING_ROLE_NAME, MANAGER_ROLE_NAME, NO_COST_QUOTA_TYPE_ATTR_NAME, QUOTA_ATTR_NAME
from .schemas import CostCenterSchema

User = get_user_model()


class CostCenter(models.Model):
    dept_id = models.CharField(max_length=60, unique=True, help_text='Unique identifier for the cost center')

    def __str__(self):
        return self.dept_id


class CostCenterAssignment(models.Model):
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name='cost_center_assignment',
        help_text='Project associated with this cost center assignment',
    )
    assignments = models.JSONField(blank=True, help_text='JSON field storing cost center assignments with percentages')
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cost Center Assignment'
        verbose_name_plural = 'Cost Center Assignments'

    def __str__(self):
        return f'Cost Center Assignment for {self.project.title}'

    def clean(self):
        """Validate the JSON field using Pydantic schema."""
        if self.assignments:
            try:
                CostCenterSchema(assignments=self.assignments)
            except Exception as e:
                raise ValidationError(f'Invalid cost center assignments: {e}')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class NoCostQuota(models.Model):
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

    quota_type = models.CharField(max_length=64, help_text='Storage quota name')
    description = models.CharField(
        max_length=128,
        blank=True,
        help_text='Human-readable description of the quota type',
    )

    amount = models.FloatField(help_text='Total quota amount')
    units = models.CharField(
        max_length=16,
        default='TB',
        help_text='Units for the quota (default: TB)',
    )

    minimum_increment = models.FloatField(help_text='Minimum allocation increment')

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'quota_type'], name='uniq_nocostquota_user_quota_type')]
        verbose_name = 'No Cost Quota'
        verbose_name_plural = 'No Cost Quotas'

    def clean(self):
        super().clean()

        allowed_units = {'TB': 0.1, 'GB': 100}
        if self.units not in allowed_units:
            raise ValidationError(
                {'units': f'Invalid units: {self.units}. Allowed: {", ".join(allowed_units.keys())}.'}
            )

        if self.minimum_increment < (required := allowed_units[self.units]):
            raise ValidationError(
                {'minimum_increment': f'Minimum allocation increment must be ≥ {required} for {self.units}.'}
            )

    def __str__(self):
        return f'{str(self.user)} - {self.quota_type}'

    def get_allotment_amount_for_allocation(self, allocation):
        """Return the allotment amount for this quota on the given allocation, or None."""
        return next(
            (
                allotment.amount
                for allotment in getattr(allocation, 'all_allotments', ())
                if allotment.no_cost_quota_id == self.pk
            ),
            None,
        )


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
    amount = models.FloatField(help_text='Allocated quota amount in TB')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['no_cost_quota', 'allocation'],
                name='uniq_nocostquotaallotment_quota_allocation',
            )
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
                status__name='Active',
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
            if self.amount < 0:
                raise ValidationError({'amount': 'Allotment amount must be greater or equal 0'})
            min_inc = self.no_cost_quota.minimum_increment
            minimum = f'{min_inc} {self.no_cost_quota.units}'
            if 0 < self.amount < min_inc:
                raise ValidationError({'amount': f'Allotment amount must be ≥ minimum increment ({minimum})'})
            # Ensure amount is a multiple of minimum_increment (with float tolerance)
            if self.amount % min_inc != 0:
                raise ValidationError(
                    {'amount': f'Allotment amount must be a multiple of minimum increment ({minimum})'}
                )

            amount = f'{self.amount} {self.no_cost_quota.units}'
            if self.amount > (ncq_amount := self.no_cost_quota.amount):
                no_cost_quota = f'{ncq_amount} {self.no_cost_quota.units}'
                raise ValidationError(
                    {
                        'amount': f'No cost quota allotment size ({amount}) is bigger than no-cost quota size ({no_cost_quota})'
                    }
                )
            allocation_quota = self.allocation.get_attribute(QUOTA_ATTR_NAME, typed=True)
            if allocation_quota is not None and self.amount > float(allocation_quota):
                raise ValidationError(
                    {
                        'amount': f'No cost quota allotment size ({amount}) is bigger than allocation size ({allocation_quota} TB)'
                    }
                )

    def __str__(self):
        return f'Allotment from {self.no_cost_quota_id} on  {str(self.allocation_id)}'
