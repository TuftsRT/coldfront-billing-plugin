from django.contrib.auth.mixins import AccessMixin, LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponseForbidden
from django.views.generic import ListView

from coldfront_billing.models import BillingScheduleHistory


class BillingScheduleHistoryListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = BillingScheduleHistory
    template_name = 'reports/billing_schedule_history.html'
    context_object_name = 'history_rows'
    ordering = ['-started', '-id']

    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return AccessMixin.handle_no_permission(self)
        return HttpResponseForbidden('You are not allowed to access this page.')
