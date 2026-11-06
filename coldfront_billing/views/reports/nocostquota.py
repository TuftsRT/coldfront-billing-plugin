import logging

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.views.decorators.http import require_GET

from coldfront_billing.forms.reports import ReportFilterForm
from coldfront_billing.reports.billing_preview import get_all_storage_allocations
from coldfront_billing.reports.nocostquota import (
    expired_storage_allocations_with_ncq_allotments,
    get_oversubscribed_no_cost_quotas,
    no_cost_quotas_report,
)
from coldfront_billing.views.utils import csv_response

logger = logging.getLogger(__name__)


def _serialize_no_cost_quotas_report(data):
    # the rows hold the Allocation instance for the template; JSON gets its id and project instead
    def row(entry):
        allocation = entry["allocation"]
        return {
            "allocation_id": allocation.id,
            "project_id": allocation.project.id,
            "project_title": allocation.project.title,
            **{key: value for key, value in entry.items() if key != "allocation"},
        }

    return {
        "allocations": [row(entry) for entry in data["allocations"]],
        "shared_allotments": [row(entry) for entry in data["shared_allotments"]],
        "errors": data["errors"],
    }


@login_required
@require_GET
def no_cost_quotas_report_view(request):
    if request.user.is_superuser:
        content_type = request.GET.get("format")
        form = ReportFilterForm(request.GET)
        if form.is_valid() and content_type != "json":
            if form.cleaned_data["username"]:
                data = no_cost_quotas_report(username=form.cleaned_data["username"])
            else:
                data = no_cost_quotas_report()
        else:
            data = no_cost_quotas_report()

        if content_type == "json":
            return JsonResponse(_serialize_no_cost_quotas_report(data), status=200)
        else:
            return TemplateResponse(
                request,
                "reports/no_cost_quotas_report.html",
                {
                    "message": data["errors"],
                    "allocations": data["allocations"],
                    "shared_allotments": data["shared_allotments"],
                    "form": form,
                },
            )
    else:
        data = no_cost_quotas_report(username=request.user.username, username_exact=True)
        return TemplateResponse(
            request,
            "reports/no_cost_quotas_report.html",
            {
                "message": data["errors"],
                "allocations": data["allocations"],
                "shared_allotments": data["shared_allotments"],
            },
        )


@user_passes_test(lambda u: u.is_superuser)
@require_GET
def oversubscribed_allotments_report(request):
    data = get_oversubscribed_no_cost_quotas()
    return TemplateResponse(request, "reports/oversubscribed_allotments_report.html", {"overages": data})


@user_passes_test(lambda u: u.is_superuser)
@require_GET
def expired_allocations_report(request):
    data = expired_storage_allocations_with_ncq_allotments()
    return TemplateResponse(request, "reports/expired_allocations_report.html", {"expired_allocations": data})


@user_passes_test(lambda u: u.is_superuser)
@require_GET
def all_allocations_allotments_report(request):
    data = get_all_storage_allocations()
    csv_data = {}
    csv_data["header"] = data[0].keys() if data else []
    csv_data["rows"] = [list(item.values()) for item in data]
    return csv_response(csv_data, filename="allocations_allotments_report.csv")
