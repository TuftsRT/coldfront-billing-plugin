import csv
from datetime import datetime

from coldfront.core.project.models import Project
from django.conf import settings
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.views import View

from coldfront_billing.constants import BILLING_ATTRIBUTE_NAME
from coldfront_billing.utils import NoStorageException, get_month_abbr
from coldfront_billing.views.mixins import BillingAllocationPrefetchMixin

ACCOUNT_NAME = getattr(
    settings,
    'COLDFRONT_BILLING_ACCOUNT_NAME',
    1234,
)
DESCRIPTION_PREFIX = getattr(
    settings,
    'COLDFRONT_BILLING_DESCRIPTION_PREFIX',
    'TTS',
)


class ExportBillingReportView(UserPassesTestMixin, BillingAllocationPrefetchMixin, View):
    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        return HttpResponseForbidden('You are not allowed to access this resource.')

    def get(self, request, *args, **kwargs):
        filename = f'report_{datetime.now().strftime("%Y-%m-%d_%H-%M")}.csv'
        month = get_month_abbr()
        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename="{filename}'},
        )

        try:
            projects = self.get_projects_prefetch(Project.objects.all())
        except NoStorageException:
            return HttpResponseNotFound('No storage resource found')

        writer = csv.writer(response)
        writer.writerow(['Account', 'DeptId', 'Project Number', 'Cost', 'Description'])

        for project in projects:
            try:
                assignments = project.cost_center_assignment.assignments or []
            except ObjectDoesNotExist:
                continue

            billing_allocations = self.create_billing_allocations(getattr(project, BILLING_ATTRIBUTE_NAME, []))
            project_cost = sum(b.total_cost for b in billing_allocations)

            if not project_cost:
                continue

            user_id = project.pi.username
            description = f'{month}-{DESCRIPTION_PREFIX}-{user_id}-{project.title}'

            for assignement in sorted(assignments, key=lambda x: x.get('department')):
                dept_id = assignement.get('department')
                pct = assignement.get('percentage')
                grant = assignement.get('grant', '')
                cost = round(project_cost * (int(pct) / 100), 2)
                writer.writerow(
                    (
                        ACCOUNT_NAME,
                        dept_id,
                        grant,
                        f'${cost}',
                        description,
                    )
                )

        return response
