from typing import Callable

from django.contrib.auth.mixins import AccessMixin, LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponseForbidden
from django.utils.dateparse import parse_date
from django.views.generic import ListView

from coldfront_billing.models import BillingScheduleHistory
from coldfront_billing.views.mixins import ListViewStateMixin


class BillingScheduleHistoryListView(LoginRequiredMixin, UserPassesTestMixin, ListViewStateMixin, ListView):
    model = BillingScheduleHistory
    template_name = "reports/billing_schedule_history.html"
    context_object_name = "history_rows"

    db_order_map = {
        "id": "id",
        "stopped": "stopped",
        "status": "status",
        "details": "details",
    }

    def get_ordering(self):
        order_by = self.request_get.get("order_by")
        direction = self.request_get.get("direction", "asc")
        if not order_by or order_by not in self.db_order_map:
            return ["-started", "-id"]
        field = self.db_order_map[order_by]
        prefix = "-" if direction == "des" else ""
        return [f"{prefix}{field}"]

    def get_queryset(self):
        qs = super().get_queryset()

        if date_from := parse_date(self.request_get.get("execution_date_from", "")):
            qs = qs.filter(stopped__date__gte=date_from)

        if date_to := parse_date(self.request_get.get("execution_date_to", "")):
            qs = qs.filter(stopped__date__lte=date_to)

        if self.request_get.get("failed_only"):
            qs = qs.exclude(status=BillingScheduleHistory.Status.SUCCESS)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_pagination_params())
        execution_date_from = self.request_get.get("execution_date_from", "")
        execution_date_to = self.request_get.get("execution_date_to", "")
        failed_only = bool(self.request_get.get("failed_only"))
        context["execution_date_from"] = execution_date_from
        context["execution_date_to"] = execution_date_to
        context["failed_only"] = failed_only
        context["history_filters_active"] = bool(execution_date_from or execution_date_to or failed_only)
        return context

    def get_object_ordering(self) -> tuple[Callable, bool]:
        pass

    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return AccessMixin.handle_no_permission(self)
        return HttpResponseForbidden("You are not allowed to access this page.")
