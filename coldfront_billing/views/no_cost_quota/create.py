from coldfront.core.allocation.models import Allocation
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View

from coldfront_billing.models import NoCostQuota, NoCostQuotaAllotment


class CreateNoCostQuotaAllotmentView(LoginRequiredMixin, View):
    """Create or update a NoCostQuotaAllotment and redirect to manage page."""

    def post(self, request):
        post = request.POST

        amount_str = request.POST.get('amount', '').strip()

        if not (quota_id := post.get('quota_id')) or not (allocation_id := post.get('allocation_id')):
            messages.error(request, 'Invalid request: missing quota or allocation.')
            return redirect('manage_no_cost_quota')

        assign_url = f'{reverse("assign_no_cost_quota")}?selected_quota={quota_id}'

        try:
            amount = float(amount_str)
        except (ValueError, TypeError):
            messages.error(request, 'Please enter a valid amount.')
            return redirect(assign_url)

        if amount <= 0:
            messages.error(request, 'Amount must be greater than zero.')
            return redirect(assign_url)

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
