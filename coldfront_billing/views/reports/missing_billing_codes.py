import logging

from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.views.decorators.http import require_GET

from ...forms import ReportFilterForm
from ...prefetch import has_billing_perm
from ...reports import missing_billing_code_report
from ...utils import sanitize_csv_value
from ...views.utils import csv_response

logger = logging.getLogger(__name__)


def _serialize_missing_billing_code(missing_billing_code):
    return [
        {
            'project_id': entry['project'].id,
            'project_title': entry['project'].title,
            'pi_username': entry['project'].pi.username,
            'project_cost': entry['project_cost'],
        }
        for entry in missing_billing_code
    ]


@user_passes_test(lambda u: u.is_authenticated and (u.is_superuser or has_billing_perm(u)))
@require_GET
def billing_code_report(request):
    """
    View for generating the missing billing code report.
    Supports JSON, CSV, and HTML response formats.
    """
    if request.user.is_superuser:
        form = ReportFilterForm(request.GET)
        if form.is_valid():
            if form.cleaned_data['username']:
                data = missing_billing_code_report(username=form.cleaned_data['username'])
            else:
                data = missing_billing_code_report()

            if request.GET.get('format') == 'json':
                return JsonResponse(
                    {
                        'missing_billing_code': _serialize_missing_billing_code(data['missing_billing_code']),
                        'total_cost': data['total_cost'],
                        'month': data['month'],
                    },
                    status=200,
                )
            elif request.GET.get('format') == 'csv':
                csv_data = {
                    'header': ['Project ID', 'Project Title', 'PI Username', 'Project Cost', 'Total Cost', 'Month'],
                    'rows': [
                        [
                            entry['project'].id,
                            sanitize_csv_value(entry['project'].title),
                            sanitize_csv_value(entry['project'].pi.username),
                            entry['project_cost'],
                            data['total_cost'],
                            data['month'],
                        ]
                        for entry in data['missing_billing_code']
                    ],
                }
                return csv_response(csv_data, filename='missing_billing_code_report.csv')
            else:
                return TemplateResponse(
                    request,
                    'reports/billing_code_report.html',
                    {
                        'missing_billing_code': data['missing_billing_code'],
                        'total_cost': data['total_cost'],
                        'month': data['month'],
                        'form': form,
                    },
                )
        else:
            return TemplateResponse(
                request, 'reports/billing_code_report.html', {'message': 'Invalid form data.'}, status=400
            )
    else:
        # accept only exact username matches
        data = missing_billing_code_report(username=request.user.username, username_exact=True)
        return TemplateResponse(
            request,
            'reports/billing_code_report.html',
            {
                'missing_billing_code': data['missing_billing_code'],
                'total_cost': data['total_cost'],
                'month': data['month'],
            },
        )
