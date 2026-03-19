from typing import Any, Dict

from coldfront.core.allocation.models import Allocation
from coldfront.core.project.models import Project
from coldfront.core.resource.models import ResourceType
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, Q, QuerySet
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView

from coldfront_billing.constants import (
    BILLING_ROLE_NAME,
    MANAGER_ROLE_NAME,
    NO_COST_QUOTA_TYPE_ATTR_NAME,
    QUOTA_ATTRIBUTE_NAME,
)
from coldfront_billing.data import NoCostQuotaAllocation
from coldfront_billing.models import NoCostQuotaAllotment
from coldfront_billing.utils import first_or_none
from coldfront_billing.views.mixins import ListViewStateMixin, PrefetchPaginationMixin
from coldfront_billing.views.no_cost_quota.common import quota_with_remaining


class AssignNoCostQuotasView(LoginRequiredMixin, PrefetchPaginationMixin, ListViewStateMixin, ListView):
    template_name = 'no_cost_quota/assign.html'
    context_object_name = 'allocation_list'
    model = Allocation

    def get(self, request, *args, **kwargs):
        if not (selected_quota := request.GET.get('selected_quota')):
            messages.error(request, 'Please select a No Cost Quota first.')
            return redirect('manage_no_cost_quota')
        self.quota = get_object_or_404(
            quota_with_remaining,
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
        quota_units = self.quota.units

        allocations = []

        for allocation in context.get('allocation_list', []):
            all_allotments = getattr(allocation, 'all_allotments', ())

            # Get quota attribute from allocation
            quota_attr_tb = first_or_none(getattr(allocation, QUOTA_ATTRIBUTE_NAME, None))
            # Check if allocation has quota_in_terabyte set
            try:
                allocation_size = float(quota_attr_tb.value) if quota_attr_tb else None
            except (TypeError, ValueError):
                allocation_size = None

            user_allotment = next((a for a in all_allotments if a.no_cost_quota.user_id == self.quota.user_id), None)
            if allocation.status.name != 'Active' and (user_allotment is None or user_allotment.amount == 0):
                continue  # skip inactive allocations without user allotment

            user_allotment_pk = user_allotment.pk if user_allotment else None

            ncq_allocation = NoCostQuotaAllocation.create(self.quota.user_id, allocation_size, all_allotments)

            other_total_quota = ncq_allocation.other_allotments_amount
            max_possible = ncq_allocation.max_possible_allocation(
                quota_remaining, quota_units, self.quota.minimum_increment
            )
            user_amount = ncq_allocation.user_amount
            first_resource = next(iter(allocation.resources.all()), None)

            allocations.append(
                {
                    'allocation': allocation,
                    'resource_name': first_resource.name if first_resource else '-',
                    'quota_amount': allocation_size or '-',
                    'other_applications': f'{other_total_quota:g} TB',
                    'user_applications': f'{ncq_allocation.user_allotment_amount:g} TB',
                    'existing_amount': f'{user_amount:g}' if user_amount else '',
                    'max_possible': max_possible,
                    'minimum_increment': self.quota.minimum_increment,
                    'allotment_id': user_allotment_pk or '',
                    'inactive': allocation.status.name != 'Active',
                }
            )

        return (
            context
            | {
                'quota': self.quota,
                'quota_remaining': quota_remaining,
                'allocations': allocations,
            }
            | self.get_pagination_params()
        )
