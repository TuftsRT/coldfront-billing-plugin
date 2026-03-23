from coldfront.core.allocation.models import Allocation
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View

from coldfront_billing.models import NoCostQuota, NoCostQuotaAllotment

REDIRECT = 'manage_no_cost_quota'


class NoCostQuotaAllotmentView(LoginRequiredMixin, View):
    """Create or update a NoCostQuotaAllotment and redirect to manage page."""

    def post(self, request):
        post = request.POST

        action = post.get('action', 'assign').strip()

        if action == 'delete':
            if not (allotment_id := post.get('allotment_id')):
                messages.error(request, 'Allotment id not passed')
                return redirect(REDIRECT)
            allotment = get_object_or_404(NoCostQuotaAllotment, pk=allotment_id)

            if not request.user.is_superuser and allotment.no_cost_quota.user_id != request.user.id:
                messages.error(request, 'You do not have permission to remove this allotment.')
                return redirect(REDIRECT)

            allotment.delete()
            messages.success(request, 'No-Cost Quota allotment deleted.')
            return redirect(REDIRECT)

        amount_str = post.get('amount', '').strip()

        if not (quota_id := post.get('quota_id')) or not (allocation_id := post.get('allocation_id')):
            messages.error(request, 'Invalid request: missing quota or allocation.')
            return redirect(REDIRECT)

        assign_url = f'{reverse("assign_no_cost_quota")}?selected_quota={quota_id}'

        try:
            amount = float(amount_str)
        except (ValueError, TypeError):
            messages.error(request, 'Please enter a valid amount.')
            return redirect(assign_url)

        quota = get_object_or_404(NoCostQuota, pk=quota_id)
        if not request.user.is_superuser and quota.user_id != request.user.id:
            messages.error(request, 'You do not have permission to assign this quota.')
            return redirect(REDIRECT)

        allocation = get_object_or_404(Allocation, pk=allocation_id)

        allotment, created = NoCostQuotaAllotment.objects.get_or_create(
            no_cost_quota=quota,
            allocation=allocation,
            defaults={'amount': amount},
        )

        if not created:
            allotment.amount = amount

        try:
            allotment.full_clean()
            allotment.save()
        except Exception as e:
            if hasattr(e, 'message_dict'):
                msg = '; '.join(f'{field}: {errors[0]}' for field, errors in e.message_dict.items())
            else:
                msg = str(e)
            messages.error(request, f'Could not save allotment: {msg}')
            return redirect(assign_url)

        action = 'Assigned' if created else 'Updated'
        messages.success(
            request,
            f'{action} {amount} {quota.units} for allocation {allocation.id}.',
        )
        return redirect(REDIRECT)
