"""The billing_cost section of ColdFront's allocation request form (coldfront_utils.allocation_request).

A request for a resource that requires payment shows a card where the requester picks the cost center
(and grant) the cost goes to, when the project has none yet. For a Storage resource the card also offers
the requester's no-cost quota and shows the estimated monthly cost as the quota is typed. The section is
saved with the allocation, before ColdFront sends its admin email and allocation_new.
"""

import logging
from functools import cached_property

from coldfront_utils.allocation_request import RequestSection, RequestSectionForm
from coldfront_utils.allocation_request.sections import active_section_classes
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from coldfront_billing.allotments import no_cost_quota_with_remaining, record_no_cost_quota_request
from coldfront_billing.models import CostCenter, CostCenterAssignment
from coldfront_billing.prefetch import can_apply_no_cost_quota

logger = logging.getLogger(__name__)

BILLING_SECTION_NAME = "billing_cost"

# The name of the quota field on the request form, which the estimate reads: storage's storage_quota
# section's, unless a site points it elsewhere. A setting, so billing doesn't import storage. Its element
# id is Django's default for that name.
QUOTA_FIELD_NAME = getattr(settings, "COLDFRONT_BILLING_QUOTA_FIELD_NAME", "storage_quota-quota")
QUOTA_FIELD_ID = f"id_{QUOTA_FIELD_NAME}"


def project_has_cost_center_assignment(project) -> bool:
    """Whether the project already has cost centers assigned."""
    try:
        return bool(project.cost_center_assignment.assignments)
    except CostCenterAssignment.DoesNotExist:
        return False


def quota_card_shown(resource, project, user, request=None) -> bool:
    """Whether the request form shows the card with the quota field (QUOTA_FIELD_NAME, by default the
    storage plugin's storage_quota section) for this request. Found through coldfront_utils' section
    registry, so billing doesn't import storage: the field's name starts with its section's name."""
    section_name = QUOTA_FIELD_NAME.split("-", 1)[0]
    for section_class in active_section_classes():
        if section_class.name == section_name:
            return section_class(resource=resource, project=project, user=user, request=request).applies()
    return False


class BillingCostForm(RequestSectionForm):
    """The cost center and grant the cost goes to, and whether to apply the requester's no-cost quota.
    BillingCostSection.build_form() drops the fields that don't apply to the request."""

    cost_center = forms.ModelChoiceField(
        queryset=CostCenter.objects.filter(cost_center_type="department").order_by("name"),
        to_field_name="name",
        label="Cost Center",
        required=False,
        widget=forms.HiddenInput(),
        help_text="The cost center the project's cost is assigned to at first. To change it or split the cost "
        'between cost centers later, use the "Billing" page under the "Project" menu. If you are not sure, '
        "leave it blank.",
    )
    grant = forms.ModelChoiceField(
        queryset=CostCenter.objects.filter(cost_center_type="grant").order_by("name"),
        to_field_name="name",
        label="Grant",
        required=False,
        widget=forms.HiddenInput(),
        help_text="The grant the project's cost is assigned to at first. Choose a cost center first.",
    )
    apply_no_cost_quota = forms.BooleanField(required=False)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("grant") and cleaned.get("cost_center") is None:
            self.add_error("grant", ValidationError("Choose a cost center before a grant."))
        return cleaned


class BillingCostSection(RequestSection):
    """The cost center, the no-cost quota and the cost estimate, for resources that require payment."""

    name = BILLING_SECTION_NAME
    order = 20
    form_class = BillingCostForm
    template = "coldfront_billing/allocation_request/cost.html"

    @cached_property
    def asks_for_quota(self):
        """Whether the quota card is on the form for this request (a Storage resource that asks for one). The
        no-cost quota and the estimate need it: the quota is what the allotment is taken from and what the
        estimate prices."""
        return self.resource.resource_type.name == "Storage" and quota_card_shown(
            self.resource, self.project, self.user, self.request
        )

    @cached_property
    def no_cost_quota(self):
        """The no-cost quota the requester may apply to this request, or None: only where the quota card is on
        the form, only for someone allowed to apply one (can_apply_no_cost_quota), and only with some left."""
        if not self.asks_for_quota or not can_apply_no_cost_quota(self.user, self.project):
            return None
        return no_cost_quota_with_remaining(self.resource, self.project, self.user)

    def applies(self):
        """Any resource that requires payment."""
        return bool(self.resource.requires_payment)

    def build_form(self, data, files=None):
        """The form, without the fields this request doesn't need: the cost center and grant when the
        project has one already, the no-cost quota when there's none to apply."""
        form = super().build_form(data, files)
        if project_has_cost_center_assignment(self.project):
            del form.fields["cost_center"]
            del form.fields["grant"]
        if self.no_cost_quota is None:
            del form.fields["apply_no_cost_quota"]
        else:
            left = self.no_cost_quota.remaining_normalized
            form.fields["apply_no_cost_quota"].label = f"Apply my no-cost quota ({left.normalize():f} TB left)"
        return form

    def card_context(self):
        return {"show_estimate": self.asks_for_quota, "quota_field_id": QUOTA_FIELD_ID}

    def save(self, allocation, form):
        """Record the no-cost quota to apply (billing's activation receiver allots it), and assign the
        project to the cost center and grant."""
        cleaned = form.cleaned_data
        # the field is only on the form when there's a quota to apply (build_form)
        if cleaned.get("apply_no_cost_quota") and not record_no_cost_quota_request(allocation, self.no_cost_quota.pk):
            # the request still goes through, without the quota
            logger.error("Allocation %s's no-cost quota wasn't recorded: its attribute type is missing", allocation.pk)
        cost_center = cleaned.get("cost_center")
        if cost_center is not None:
            assignment = {"department": cost_center.name, "percentage": 100}
            if grant := cleaned.get("grant"):
                assignment["grant"] = grant.name
            CostCenterAssignment.objects.update_or_create(project=self.project, defaults={"assignments": [assignment]})
