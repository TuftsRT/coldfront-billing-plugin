from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import JsonResponse
from django.views import View

from coldfront_billing.models import BillingScheduleSettings
from coldfront_billing.reports import auto_assign_quota, send_billing_report_email


class SendReportView(UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        return JsonResponse(
            {
                'success': False,
                'message': 'You are not allowed to access this resource.',
            },
            status=403,
        )

    def get(self, *_, **__):
        billing_settings = BillingScheduleSettings.objects.first()
        if billing_settings.autoassign_no_cost_quota:
            auto_assign_quota()
        result = send_billing_report_email(billing_settings)
        return JsonResponse(result, status=200 if result['success'] else 400)
