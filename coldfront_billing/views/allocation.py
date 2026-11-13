from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import View

from coldfront.core.allocation.models import (
    Allocation,
    AllocationPermission,
)
from coldfront.core.allocation.utils import get_user_resources
from coldfront.core.allocation.views import AllocationChangeView as ColdfrontAllocationChangeView
from coldfront.core.project.models import Project, ProjectPermission
from coldfront.core.resource.models import ResourceType

from coldfront_billing.allotments import no_cost_quota_with_remaining, record_no_cost_quota_request
from coldfront_billing.constants import (
    COST_ATTR_NAME,
    DEFAULT_BILLING_COST,
    DEFAULT_BILLING_QUOTA,
    STORAGE_RESOURCE_ATTRIBUTE_NAME,
)
from coldfront_billing.data.billing import BillingAllocation, monthly_cost, predicted_monthly_cost
from coldfront_billing.data.common import parse_cost_per_tb
from coldfront_billing.prefetch import (
    can_apply_no_cost_quota,
    get_no_cost_quota_allotments_prefetch,
    get_paid_storage_resources_prefetch,
    get_quota_attr_prefetch,
)
from coldfront_billing.request_section import QUOTA_FIELD_NAME, BillingCostSection
from coldfront_billing.utils import first_or_none


class AllocationCostPreviewView(LoginRequiredMixin, UserPassesTestMixin, View):
    """JSON endpoint: estimated total cost for a storage quota (TB) before completing the allocation."""

    def test_func(self):
        allocation = get_object_or_404(Allocation, pk=self.kwargs["pk"])
        if self.request.user.has_perm("allocation.can_view_all_allocations"):
            return True
        return allocation.has_perm(self.request.user, AllocationPermission.USER)

    def get(self, request, *args, **kwargs):
        try:
            quota_tb = Decimal(request.GET["quota_in_terabyte"])
        except (KeyError, TypeError, ValueError):
            return JsonResponse({"error": "quota_in_terabyte is required and must be a number."}, status=400)
        if quota_tb < 0:
            return JsonResponse({"error": "quota_in_terabyte must be zero or positive."}, status=400)

        storage_type = ResourceType.objects.only("id").filter(name="Storage").first()
        if not storage_type:
            return JsonResponse({"error": "Storage resource type is not configured."}, status=500)

        allocation = get_object_or_404(
            Allocation.objects.select_related("project", "status").prefetch_related(
                get_paid_storage_resources_prefetch(storage_type.id),
                get_no_cost_quota_allotments_prefetch(),
                get_quota_attr_prefetch(),
            ),
            pk=kwargs["pk"],
        )

        remaining_quota = 0
        quota_id = None
        storage_resource = first_or_none(getattr(allocation, STORAGE_RESOURCE_ATTRIBUTE_NAME, []))
        if storage_resource and (
            no_cost_quota := no_cost_quota_with_remaining(storage_resource, allocation.project, request.user)
        ):
            remaining_quota = no_cost_quota.remaining_normalized
            quota_id = no_cost_quota.id

        billing = BillingAllocation.parse(allocation, DEFAULT_BILLING_QUOTA, DEFAULT_BILLING_COST, quota_tb)

        response = {
            "total_cost": billing.total_cost,
            "quota_cost": billing.calculate_cost(quota_tb),
            "cost_per_tb": billing.cost_per_tb,
            "quota_tb": quota_tb,
        }

        if quota_id:
            reduced_cost, applied_quota_amount = billing.get_predicted_cost(remaining_quota)
            response.update(
                {
                    "quota_id": quota_id,
                    "applied_quota": applied_quota_amount,
                    "reduced_cost": reduced_cost,
                }
            )

        return JsonResponse(response)


class BillingAllocationChangeView(ColdfrontAllocationChangeView):
    """
    ColdFront ``AllocationChangeView`` plus ``apply_allocation_quota`` POST (same as solution 1:
    extend the allocation-change handler to set ``ALLOCATION_QUOTA_ATTRIBUTE_NAME`` on success).
    """

    def post(self, request, *args, **kwargs):
        apply_quota_raw = request.POST.get("apply_allocation_quota", "").strip()
        pk = self.kwargs.get("pk")
        response = super().post(request, *args, **kwargs)
        if apply_quota_raw and pk is not None and self._is_successful_change_submission(response, pk):
            allocation = get_object_or_404(Allocation, pk=pk)
            if not can_apply_no_cost_quota(request.user, allocation.project):
                messages.warning(request, "You do not have permission to apply a quota to this allocation.")
            elif not record_no_cost_quota_request(allocation, apply_quota_raw):
                messages.warning(request, "Quota application preference could not be saved. Please contact support.")
        return response

    @staticmethod
    def _is_successful_change_submission(response: HttpResponse, allocation_pk: int | str) -> bool:
        if not isinstance(response, HttpResponseRedirect):
            return False
        expected = reverse("allocation-detail", kwargs={"pk": allocation_pk})
        location = response.url
        path = urlparse(location).path if location.startswith(("http://", "https://")) else location
        return path.rstrip("/") == expected.rstrip("/")


class RequestCostEstimateView(LoginRequiredMixin, UserPassesTestMixin, View):
    """The billing_cost card's estimate on the allocation request form, for the quota typed into the quota
    field: an HTML fragment htmx swaps into the card. Admits whoever may use the project's request page."""

    def test_func(self):
        self.project = get_object_or_404(Project, pk=self.kwargs["project_pk"])
        return self.project.has_perm(self.request.user, ProjectPermission.UPDATE)

    def get(self, request, *args, **kwargs):
        resource_pk = request.GET.get("resource", "")
        if not resource_pk.isdigit():
            raise Http404("No such resource")
        resource = get_object_or_404(get_user_resources(request.user).select_related("resource_type"), pk=resource_pk)
        section = BillingCostSection(resource=resource, project=self.project, user=request.user, request=request)
        # only where the card shows an estimate: a paid resource whose request asks for a quota
        if not (section.applies() and section.asks_for_quota):
            raise Http404("No estimate for this resource")

        template = "coldfront_billing/allocation_request/cost_estimate.html"
        quota = requested_quota(request.GET.get(QUOTA_FIELD_NAME, ""))
        if quota is None:
            return render(request, template, {"quota": None})
        cost_per_tb = parse_cost_per_tb(
            resource.get_attribute(COST_ATTR_NAME, expand=False, typed=False), DEFAULT_BILLING_COST
        )
        try:
            context = {"quota": quota, "cost_per_tb": cost_per_tb, "total_cost": monthly_cost(quota, cost_per_tb)}
            if section.no_cost_quota is not None:
                reduced_cost, applied = predicted_monthly_cost(
                    quota, cost_per_tb, section.no_cost_quota.remaining_normalized
                )
                if applied > 0:
                    context.update(reduced_cost=reduced_cost, applied_quota=applied.normalize())
        except InvalidOperation:
            context = {"quota": None}  # too large to price (1e30, say): the quota field refuses it anyway
        return render(request, template, context)


def requested_quota(value: str):
    """The quota typed into the request form, in TB, or None unless it's a finite number above zero."""
    try:
        quota = Decimal(value.strip())
    except InvalidOperation:
        return None
    return quota if quota.is_finite() and quota > 0 else None
