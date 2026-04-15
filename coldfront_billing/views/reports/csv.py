from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.views import View

from coldfront_billing.utils import NoStorageException
from coldfront_billing.views.reports.create import CreateReportMixin


class ExportBillingReportView(UserPassesTestMixin, CreateReportMixin, View):
    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        return HttpResponseForbidden('You are not allowed to access this resource.')

    def get(self, request, *args, **kwargs):
        try:
            filename, csv_content = self.create_report()
        except NoStorageException:
            return HttpResponseNotFound('No storage resource found')

        response = HttpResponse(
            csv_content,
            content_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'},
        )
        return response
