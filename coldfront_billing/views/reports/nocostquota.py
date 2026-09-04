import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.views.decorators.http import require_GET

from coldfront_billing.forms.reports import ReportFilterForm
from coldfront_billing.reports.nocostquota import no_cost_quotas_report

logger = logging.getLogger(__name__)


@login_required
@require_GET
def no_cost_quotas_report_view(request):
    if request.user.is_superuser:
        content_type = request.GET.get('format')
        form = ReportFilterForm(request.GET)
        if form.is_valid() and content_type != 'json':
            if form.cleaned_data['username']:
                data = no_cost_quotas_report(username=form.cleaned_data['username'])
            else:
                data = no_cost_quotas_report()
        else:
            data = no_cost_quotas_report()

        if content_type == 'json':
            return JsonResponse(data, status=200)
        else:
            return TemplateResponse(
                request,
                'reports/no_cost_quotas_report.html',
                {
                    'message': data['errors'],
                    'allocations': data['allocations'],
                    'shared_allotments': data['shared_allotments'],
                    'form': form,
                },
            )
    else:
        data = no_cost_quotas_report(username=request.user.username, username_exact=True)
        return TemplateResponse(
            request,
            'reports/no_cost_quotas_report.html',
            {
                'message': data['errors'],
                'allocations': data['allocations'],
                'shared_allotments': data['shared_allotments'],
            },
        )
