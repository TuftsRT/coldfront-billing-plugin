import logging

from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.views.decorators.http import require_GET

from ...forms import ReportFilterForm
from ...prefetch import has_billing_perm
from ...reports import get_cost_previews
from ...utils import sanitize_csv_value
from ...views.utils import csv_response

logger = logging.getLogger(__name__)


@user_passes_test(lambda u: u.is_authenticated and (u.is_superuser or has_billing_perm(u)))
@require_GET
def charge_report(request):
    """
    View for generating the charge report.
    Supports JSON, CSV, and HTML response formats.
    """
    if request.user.is_superuser:
        form = ReportFilterForm(request.GET)
        if form.is_valid():
            username = form.cleaned_data['username']
            billing_code = form.cleaned_data['billing_code']
            data = get_cost_previews(username=username, billing_code=billing_code)

            if request.GET.get('format') == 'json':
                # serialize the data for JSON response
                response = {
                    'charge_report': [
                        {
                            'project_id': entry['project'].id,
                            'project': entry['project'].title,
                            'owner': entry['project'].pi.username,
                            'project_cost': entry['project_cost'],
                        }
                        for entry in data['charge_report']
                    ],
                    'missing_billing_codes': [
                        {
                            'project_id': entry['project'].id,
                            'project': entry['project'].title,
                            'owner': entry['project'].pi.username,
                            'project_cost': entry['project_cost'],
                        }
                        for entry in data['missing_billing_code']
                    ],
                    'total_cost': data['total_cost'],
                    'month': data['month'],
                }
                return JsonResponse(response, status=200)
            elif request.GET.get('format') == 'csv':
                # serialize data for csv response. format should parallel the billing report structure
                csv_data = {
                    'header': ['DeptId', 'Project Number', 'Cost', 'Project Description', 'UTLN', 'Full Name'],
                    'rows': [
                        [
                            sanitize_csv_value(entry['department']),
                            sanitize_csv_value(entry['grant']),
                            entry['project_cost'],
                            sanitize_csv_value(entry['project'].title),
                            sanitize_csv_value(entry['project'].pi.username),
                            sanitize_csv_value(f'{entry["project"].pi.first_name} {entry["project"].pi.last_name}'),
                        ]
                        for entry in data['charge_report']
                    ],
                }
                return csv_response(csv_data, filename=f'charge_report_{data["month"].lower().strip()}.csv')
            else:
                return TemplateResponse(
                    request,
                    'reports/charge_report.html',
                    {
                        'charge_report': data['charge_report'],
                        'total_cost': data['total_cost'],
                        'month': data['month'],
                        'form': form,
                    },
                )
        else:
            return TemplateResponse(
                request, 'reports/charge_report.html', {'message': 'Invalid form data.'}, status=400
            )
    else:
        form = ReportFilterForm(request.GET)
        if form.is_valid():
            billing_code = form.cleaned_data['billing_code']
            data = get_cost_previews(username=request.user.username, billing_code=billing_code, username_exact=True)
            return TemplateResponse(
                request,
                'reports/charge_report.html',
                {
                    'charge_report': data['charge_report'],
                    'total_cost': data['total_cost'],
                    'month': data['month'],
                    'form': form,
                },
            )
        else:
            return TemplateResponse(
                request, 'reports/charge_report.html', {'message': 'Invalid form data.'}, status=400
            )
