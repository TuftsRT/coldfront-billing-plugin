from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.views import View

from coldfront_billing.models import BillingScheduleSettings
from coldfront_billing.reports import auto_assign_quota, create_csv_report
from coldfront_billing.utils import NoStorageException


class ExportBillingReportView(UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        return HttpResponseForbidden('You are not allowed to access this resource.')

    def get(self, request, *args, **kwargs):
        billing_settings = BillingScheduleSettings.objects.first()
        if billing_settings and billing_settings.autoassign_no_cost_quota:
            auto_assign_quota()
        try:
            filename, csv_content = create_csv_report()
        except NoStorageException:
            return HttpResponseNotFound('No storage resource found')

        response = HttpResponse(
            csv_content,
            content_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'},
        )
        return response
