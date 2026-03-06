from typing import Any, Dict

from coldfront.core.allocation.models import Allocation
from coldfront.core.project.models import Project
from coldfront.core.resource.models import ResourceType
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F, FloatField, Prefetch, Q, QuerySet, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import ListView

from coldfront_billing.constants import (
    BILLING_ROLE_NAME,
    MANAGER_ROLE_NAME,
    NO_COST_QUOTA_TYPE_ATTR_NAME,
)
from coldfront_billing.models import NoCostQuota, NoCostQuotaAllotment

from .mixins import BillingAllocationPrefetchMixin


class ManageNoCostQuotasView(LoginRequiredMixin, ListView):
    template_name = 'no_cost_quota/manage.html'
    context_object_name = 'quota_list'
    model = NoCostQuota

    def get_queryset(self) -> QuerySet[NoCostQuota]:
        qs = (
            NoCostQuota.objects.select_related('user')
            .annotate(
                used=Coalesce(Sum('allotments__amount'), Value(0, output_field=FloatField())),
            )
            .annotate(
                remaining=F('amount') - F('used'),
            )
            .order_by('user__username', 'quota_type')
        )

        if not self.request.user.is_superuser:
            qs = qs.filter(user=self.request.user)

        return qs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['quota_count'] = len(context.get('quota_list', []))

        return context


class AssignNoCostQuotasView(LoginRequiredMixin, BillingAllocationPrefetchMixin, ListView):
    template_name = 'no_cost_quota/assign.html'
    context_object_name = 'allocation_list'
    model = Allocation

    def get(self, request, *args, **kwargs):
        if not (selected_quota := request.GET.get('selected_quota')):
            messages.error(request, 'Please select a No Cost Quota first.')
            return redirect('manage_no_cost_quota')
        self.quota = get_object_or_404(NoCostQuota, pk=selected_quota)
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
        used = NoCostQuotaAllotment.objects.filter(no_cost_quota=self.quota).aggregate(
            total=Coalesce(Sum('amount'), Value(0, output_field=FloatField()))
        )['total']
        context['quota'] = self.quota
        context['quota_remaining'] = self.quota.amount - used
        context['allocation_count'] = len(context.get('allocation_list', []))

        current_user_id = self.request.user.id
        allocation_list_with_allotments = []
        for allocation in context.get('allocation_list', []):
            other_parts = []
            current_parts = []
            for a in getattr(allocation, 'all_allotments', []):
                part = f'{a.amount} {a.no_cost_quota.units}'
                if a.no_cost_quota.user_id == current_user_id:
                    current_parts.append(part)
                else:
                    other_parts.append(part)
            other_users_display = ', '.join(other_parts) if other_parts else '-'
            current_user_display = ', '.join(current_parts) if current_parts else '-'
            allocation_list_with_allotments.append(
                {
                    'allocation': allocation,
                    'other_users_display': other_users_display,
                    'current_user_display': current_user_display,
                }
            )
        context['allocation_list_with_allotments'] = allocation_list_with_allotments

        return context


class CreateNoCostQuotaAllotmentView(LoginRequiredMixin, View):
    """Create or update a NoCostQuotaAllotment and redirect to manage page."""

    def post(self, request):
        quota_id = request.POST.get('quota_id')
        allocation_id = request.POST.get('allocation_id')
        amount_str = request.POST.get('amount', '').strip()

        if not quota_id or not allocation_id:
            messages.error(request, 'Invalid request: missing quota or allocation.')
            return redirect('manage_no_cost_quota')

        try:
            amount = float(amount_str)
        except (ValueError, TypeError):
            messages.error(request, 'Please enter a valid amount.')
            return redirect(f'{reverse("assign_no_cost_quota")}?selected_quota={quota_id}')

        if amount <= 0:
            messages.error(request, 'Amount must be greater than zero.')
            return redirect(f'{reverse("assign_no_cost_quota")}?selected_quota={quota_id}')

        quota = get_object_or_404(NoCostQuota, pk=quota_id)
        if not request.user.is_superuser and quota.user_id != request.user.id:
            messages.error(request, 'You do not have permission to assign this quota.')
            return redirect('manage_no_cost_quota')

        allocation = get_object_or_404(Allocation, pk=allocation_id)

        existing_allotment = NoCostQuotaAllotment.objects.filter(
            no_cost_quota=quota,
            allocation=allocation,
        ).first()

        if existing_allotment:
            allotment = existing_allotment
            allotment.amount = amount
            is_update = True
        else:
            allotment = NoCostQuotaAllotment(
                no_cost_quota=quota,
                allocation=allocation,
                amount=amount,
            )
            is_update = False

        try:
            allotment.full_clean()
            allotment.save()
        except Exception as e:
            if hasattr(e, 'message_dict'):
                msg = '; '.join(f'{k}: {v[0]}' for k, v in e.message_dict.items())
            else:
                msg = str(e)
            messages.error(request, f'Could not save allotment: {msg}')
            assign_url = reverse('assign_no_cost_quota') + f'?selected_quota={quota_id}'
            return redirect(assign_url)

        action = 'Updated' if is_update else 'Assigned'
        messages.success(request, f'{action} {amount} {quota.units} for allocation {allocation_id}.')
        return redirect('manage_no_cost_quota')
