from typing import Any, Dict

from coldfront.core.allocation.models import Allocation
from coldfront.core.project.models import Project
from coldfront.core.resource.models import ResourceType
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F, FloatField, Prefetch, Q, QuerySet, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView

from coldfront_billing.constants import (
    BILLING_ROLE_NAME,
    MANAGER_ROLE_NAME,
    NO_COST_QUOTA_TYPE_ATTR_NAME,
    QUOTA_ATTRIBUTE_NAME,
)
from coldfront_billing.data import UNIT_TO_TB, BillingNoCostQuota, StorageUnit
from coldfront_billing.models import NoCostQuota, NoCostQuotaAllotment
from coldfront_billing.utils import first_or_none
from coldfront_billing.views.mixins import BillingAllocationPrefetchMixin


def sum_allotments(allotments) -> float:
    """Sum allotment amounts normalized to TB. Unknown units default to TB."""
    return round(
        sum(
            BillingNoCostQuota.create(
                allotment.amount,
                getattr(allotment.no_cost_quota, 'units', None) or 'TB',
            ).normalized_amount
            for allotment in allotments
        ),
        2,
    )


class AssignNoCostQuotasView(LoginRequiredMixin, BillingAllocationPrefetchMixin, ListView):
    template_name = 'no_cost_quota/assign.html'
    context_object_name = 'allocation_list'
    model = Allocation

    def get(self, request, *args, **kwargs):
        if not (selected_quota := request.GET.get('selected_quota')):
            messages.error(request, 'Please select a No Cost Quota first.')
            return redirect('manage_no_cost_quota')
        self.quota = get_object_or_404(
            NoCostQuota.objects.annotate(
                used=Coalesce(Sum('allotments__amount'), Value(0, output_field=FloatField())),
            ).annotate(remaining=F('amount') - F('used')),
            pk=selected_quota,
        )
        if not request.user.is_superuser and self.quota.user_id != request.user.id:
            messages.error(request, 'You do not have permission to assign this quota.')
            return redirect('manage_no_cost_quota')
        return super().get(request, *args, **kwargs)

    def get_queryset(self) -> QuerySet[Allocation]:
        quota_type = self.quota.quota_type
        quota_owner = self.quota.user
        storage_type = ResourceType.objects.only('id').filter(name='Storage').first()

        if not storage_type:
            return Allocation.objects.none()

        allocations = Allocation.objects.filter(
            resources__resource_type_id=storage_type.id,
            resources__requires_payment=True,
            resources__resourceattribute__resource_attribute_type__name=NO_COST_QUOTA_TYPE_ATTR_NAME,
            resources__resourceattribute__value=quota_type,
            status__name='Active',
            project__in=Project.objects.filter(
                Q(pi=quota_owner)
                | Q(
                    projectuser__user=quota_owner,
                    projectuser__role__name__in=[BILLING_ROLE_NAME, MANAGER_ROLE_NAME],
                    projectuser__status__name='Active',
                )
            ),
        ).distinct()

        allotments_prefetch = Prefetch(
            'no_cost_quota_allotments',
            queryset=NoCostQuotaAllotment.objects.select_related('no_cost_quota').only(
                'id',
                'allocation_id',
                'amount',
                'no_cost_quota_id',
                'no_cost_quota__user_id',
                'no_cost_quota__units',
            ),
            to_attr='all_allotments',
        )
        return (
            allocations.select_related('project', 'project__pi', 'status')
            .prefetch_related(
                'resources',
                self.get_quota_attr_prefetch(),
                allotments_prefetch,
            )
            .order_by('project__title', 'pk')
        )

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        quota_remaining = round(self.quota.remaining, 2)

        allocations = []
        user_id = self.request.user.id

        # Allocation quota is always in TB - needs to normalize quota unit
        tb_to_quota_unit = 1.0 / UNIT_TO_TB[StorageUnit.parse(self.quota.units)]

        for allocation in context.get('allocation_list', []):
            all_allotments = getattr(allocation, 'all_allotments', ())
            user_allotments = [a for a in all_allotments if a.no_cost_quota.user_id == user_id]
            other_allotments = [a for a in all_allotments if a.no_cost_quota.user_id != user_id]

            user_total_tb = sum_allotments(user_allotments)
            other_total_tb = sum_allotments(other_allotments)
            total_applied_tb = user_total_tb + other_total_tb

            first_resource = next(iter(allocation.resources.all()), None)

            quota_attrs = getattr(allocation, QUOTA_ATTRIBUTE_NAME, None)
            first_quota_attr = first_or_none(quota_attrs)

            # Check if allocation has quota_in_terabyte set
            try:
                allocation_quota_tb = float(first_quota_attr.value) if first_quota_attr else None
            except (TypeError, ValueError):
                allocation_quota_tb = None

            # Get existing allotments from current no-cost quota on allocation
            amount = self.quota.get_allotment_amount_for_allocation(allocation)
            quota_remaining += amount or 0

            if allocation_quota_tb is not None:
                allocation_available_tb = max(0, allocation_quota_tb - total_applied_tb)
                allocation_available = allocation_available_tb * tb_to_quota_unit
                max_possible = round(min(quota_remaining, allocation_available), 2)
            else:
                max_possible = round(quota_remaining, 2)

            existing_amount = f'{amount:g}' if amount is not None else ''

            allocations.append(
                {
                    'allocation': allocation,
                    'resource_name': first_resource.name if first_resource else '-',
                    'status_name': allocation.status.name,
                    'quota_amount': first_quota_attr.value if first_quota_attr else '-',
                    'others_applied': f'{other_total_tb:g} TB',
                    'my_applied': f'{user_total_tb:g} TB',
                    'existing_amount': existing_amount,
                    'max_possible': max_possible,
                    'minimum_increment': self.quota.minimum_increment,
                }
            )

        return context | {
            'quota': self.quota,
            'quota_remaining': quota_remaining,
            'allocations': allocations,
        }
