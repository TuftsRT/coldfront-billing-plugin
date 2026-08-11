from decimal import ROUND_FLOOR, Decimal
from typing import Any, Dict

from coldfront.core.allocation.models import Allocation
from coldfront.core.project.models import Project
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView

from coldfront_billing.constants import (
    ALLOTMENTS_ATTRIBUTE_NAME,
)
from coldfront_billing.data import NoCostQuotaAllocation
from coldfront_billing.data.quota import NoCostQuotaEngine
from coldfront_billing.enums import AllocationStatus
from coldfront_billing.forms import AllocationSearchForm
from coldfront_billing.prefetch import get_filtered_allocations_prefetch
from coldfront_billing.views.mixins import NoCostQuotaAssignViewMixin
from coldfront_billing.views.no_cost_quota.common import quota_with_remaining


class AssignNoCostQuotasView(LoginRequiredMixin, NoCostQuotaAssignViewMixin, ListView):
    template_name = 'no_cost_quota/assign.html'
    context_object_name = 'allocation_list'
    model = Allocation

    @property
    def filtered_allocations(self) -> QuerySet[Allocation]:
        search_form = AllocationSearchForm(self.request.GET)
        allocations = self.get_queryset()
        if search_form.is_valid():
            if project := search_form.cleaned_data.get('project'):
                allocations = [a for a in allocations if project.lower() in (a.project.title or '').lower()]

            status = search_form.cleaned_data.get('status')
            match status:
                case 'active':
                    allocations = [a for a in allocations if a.status.name == AllocationStatus.ACTIVE]
                case 'inactive':
                    allocations = [a for a in allocations if a.status.name != AllocationStatus.ACTIVE]
                case _:
                    pass

        return allocations

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
        return get_filtered_allocations_prefetch(self.quota)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        quota_remaining = Decimal(self.quota.remaining).quantize(Decimal('0.01'), rounding=ROUND_FLOOR)
        quota_units = self.quota.units

        auto_assign_allocations = self.get_queryset().filter(
            project__in=Project.objects.filter(Q(pi=self.quota.user)),
        )

        ncq_engine = NoCostQuotaEngine(self.quota.user_id, auto_assign_allocations)
        assignments = ncq_engine.auto_assign(
            quota_remaining,
            quota_units,
            self.quota.increment_gb,
        )

        allocation_objs = list(self.filtered_allocations)
        allocations = []

        for allocation in allocation_objs:
            all_allotments = getattr(allocation, ALLOTMENTS_ATTRIBUTE_NAME, ())

            ncq_allocation = NoCostQuotaAllocation.create(self.quota.user_id, allocation)

            user_allotment = next((a for a in all_allotments if a.no_cost_quota.user_id == self.quota.user_id), None)
            if allocation.status.name != AllocationStatus.ACTIVE and (
                user_allotment is None or user_allotment.amount == 0
            ):
                continue  # skip inactive allocations without user allotment

            user_allotment_pk = user_allotment.pk if user_allotment else None

            other_total_quota = ncq_allocation.other_allotments_amount
            max_possible = ncq_allocation.max_possible_allocation(
                quota_remaining, quota_units, self.quota.increment_gb
            )
            user_amount = ncq_allocation.user_amount.amount
            first_resource = next(iter(allocation.resources.all()), None)

            auto_assign_allocation = next((a for a in assignments if a.allocation_id == allocation.id), None)
            auto_assign_amount = auto_assign_allocation.amount if auto_assign_allocation else 0

            allocations.append(
                {
                    'allocation': allocation,
                    'resource_name': first_resource.name if first_resource else '-',
                    'quota_amount': ncq_allocation.allocation_amount or '-',
                    'other_applications': f'{other_total_quota:g} TB',
                    'user_applications': f'{ncq_allocation.user_allotment_amount:g} TB',
                    'existing_amount': f'{user_amount:g}' if user_amount else '',
                    'max_possible': max_possible,
                    'increment_tb': self.quota.increment_gb / 1000,
                    'allotment_id': user_allotment_pk or '',
                    'inactive': allocation.status.name != AllocationStatus.ACTIVE,
                    'auto_assign_amount': auto_assign_amount,
                }
            )

        key_func, reverse = self.get_object_ordering()
        allocations = sorted(allocations, key=key_func, reverse=reverse)
        auto_assign_preview = [row for row in allocations if row['auto_assign_amount'] > 0]
        self.quota.increment_tb = self.quota.increment_gb / 1000
        return (
            context
            | {
                'quota': self.quota,
                'quota_remaining': quota_remaining,
                'search_form': AllocationSearchForm(self.request.GET),
                'auto_assign_preview': auto_assign_preview,
                'assignments': assignments,
                'back': self.request.GET.get('back', ''),
                'show_auto_assign': len(auto_assign_allocations) > 0 or self.request.user.is_superuser,
            }
            | self.get_extended_pagination_params(allocations)
        )
