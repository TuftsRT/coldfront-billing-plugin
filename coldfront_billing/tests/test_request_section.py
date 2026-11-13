"""The billing_cost section: a paid request's cost center and no-cost quota, on ColdFront's request form."""

import pytest
from coldfront_utils.allocation_request import sections
from coldfront_utils.allocation_request.forms import SECTIONS_CONTAINER_ID
from coldfront_utils.allocation_request.views import AllocationRequestCreateView
from django.apps import apps as global_apps
from django.urls import NoReverseMatch, reverse

from coldfront.core.allocation import views as allocation_views
from coldfront.core.allocation.models import Allocation, AllocationStatusChoice, AllocationUserStatusChoice
from coldfront.core.project.models import ProjectUser
from coldfront.core.resource.models import AttributeType as ResourceAttributeTypeBase
from coldfront.core.resource.models import Resource, ResourceAttribute, ResourceAttributeType, ResourceType

from coldfront_billing import checks as billing_checks
from coldfront_billing.constants import ALLOCATION_QUOTA_ATTRIBUTE_NAME
from coldfront_billing.models import CostCenter, CostCenterAssignment
from coldfront_billing.request_section import (
    BILLING_SECTION_NAME,
    QUOTA_FIELD_ID,
    QUOTA_FIELD_NAME,
    BillingCostSection,
)
from coldfront_billing.tests.quota_section_stand_in import StandInQuotaSection

# configure_urls: billing's URLs, which the card and the estimate use
pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("configure_urls")]


@pytest.fixture(autouse=True)
def quota_card(monkeypatch):
    """The storage plugin's quota section, as a stand-in: billing reads the quota from its card. Tests of a
    request without that card take it out of the registry."""
    monkeypatch.setitem(sections._registry, StandInQuotaSection.name, StandInQuotaSection)


def without_the_quota_card(monkeypatch):
    monkeypatch.delitem(sections._registry, StandInQuotaSection.name)


def set_not_to_ask_for_a_quota(resource):
    ResourceAttribute.objects.create(
        resource=resource,
        resource_attribute_type=ResourceAttributeType.objects.get_or_create(
            name="quota_on_request",
            defaults={"attribute_type": ResourceAttributeTypeBase.objects.get_or_create(name="Yes/No")[0]},
        )[0],
        value="No",
    )


CARDS_REQUEST = {"HX-Request": "true", "HX-Target": SECTIONS_CONTAINER_ID}


def paid_resource(type_name, name="Tier 1 HPC", no_cost_quota_type=None, quota_type_attribute=None):
    resource = Resource.objects.create(
        resource_type=ResourceType.objects.get_or_create(name=type_name)[0],
        name=name,
        description="",
        requires_payment=True,
    )
    if no_cost_quota_type is not None:
        ResourceAttribute.objects.create(
            resource=resource, resource_attribute_type=quota_type_attribute, value=no_cost_quota_type
        )
    return resource


@pytest.fixture
def paid_storage(storage_resource_type, no_cost_quota_type_attribute_type):
    """Paid storage whose no-cost quota type is no_cost_quota's (tier_1)."""
    return paid_resource("Storage", no_cost_quota_type="tier_1", quota_type_attribute=no_cost_quota_type_attribute_type)


@pytest.fixture
def billed_compute(no_cost_quota_type_attribute_type):
    """A paid resource that isn't storage, even with a no-cost quota type."""
    return paid_resource(
        "Cluster", "GPU Hours", no_cost_quota_type="tier_1", quota_type_attribute=no_cost_quota_type_attribute_type
    )


@pytest.fixture
def billing_user(user, project, billing_role, project_user_status_active):
    """`user`, who has no_cost_quota, with the Billing role on the project: allowed to apply it."""
    ProjectUser.objects.create(project=project, user=user, role=billing_role, status=project_user_status_active)
    return user


@pytest.fixture
def grant_center(db):
    return CostCenter.objects.create(name="NIH_R01", cost_center_type="grant")


def request_cards(client, project, resource):
    """Ask the request page for `resource`'s cards, as its resource drop-down does."""
    return client.get(reverse("allocation-create", args=[project.pk]), {"resource": resource.pk}, headers=CARDS_REQUEST)


def section_for(resource, project, user):
    return BillingCostSection(resource=resource, project=project, user=user)


def form_for(resource, project, user, data=None):
    return section_for(resource, project, user).build_form(data)


# -- Registration and which requests show it ------------------------------------------------------


def test_the_section_is_registered_when_the_app_is_ready():
    assert sections._registry[BILLING_SECTION_NAME] is BillingCostSection


def test_any_paid_resource_shows_the_card(project, pi_user, paid_storage, billed_compute):
    assert section_for(paid_storage, project, pi_user).applies() is True
    assert section_for(billed_compute, project, pi_user).applies() is True


def test_a_free_resource_doesnt(project, pi_user, storage_resource_type):
    free = Resource.objects.create(resource_type=storage_resource_type, name="Course", requires_payment=False)

    assert section_for(free, project, pi_user).applies() is False


# -- Which fields the card has ----------------------------------------------------------------------


def test_a_project_without_a_cost_center_is_asked_for_one(project, pi_user, paid_storage):
    form = form_for(paid_storage, project, pi_user)

    assert {"cost_center", "grant"} <= set(form.fields)


def test_a_project_with_a_cost_center_isnt(project, pi_user, paid_storage, cost_center_assignment):
    form = form_for(paid_storage, project, pi_user)

    assert "cost_center" not in form.fields and "grant" not in form.fields


def test_storage_offers_the_requesters_no_cost_quota(project, billing_user, paid_storage, no_cost_quota):
    form = form_for(paid_storage, project, billing_user)

    assert "apply_no_cost_quota" in form.fields
    assert "100" in str(form.fields["apply_no_cost_quota"].label)  # TB left


def test_a_superuser_requesting_is_offered_the_pis_no_cost_quota(
    project, superuser, pi_user, paid_storage, no_cost_quota
):
    no_cost_quota.user = pi_user
    no_cost_quota.save()

    assert "apply_no_cost_quota" in form_for(paid_storage, project, superuser).fields


@pytest.mark.parametrize(
    "case", ["no quota left", "not storage", "no billing permission"], ids=lambda case: case.replace(" ", "_")
)
def test_no_cost_quota_isnt_offered(
    project, user, billing_role, project_user_status_active, paid_storage, billed_compute, no_cost_quota, case
):
    if case != "no billing permission":
        ProjectUser.objects.create(project=project, user=user, role=billing_role, status=project_user_status_active)
    if case == "no quota left":
        no_cost_quota.delete()
    resource = billed_compute if case == "not storage" else paid_storage

    assert "apply_no_cost_quota" not in form_for(resource, project, user).fields


@pytest.mark.parametrize("why", ["not registered", "set not to ask"])
def test_no_cost_quota_isnt_offered_without_the_quota_card(
    project, billing_user, paid_storage, no_cost_quota, monkeypatch, why
):
    """Nothing would save the quota it's allotted from."""
    if why == "not registered":
        without_the_quota_card(monkeypatch)
    else:
        set_not_to_ask_for_a_quota(paid_storage)

    form = form_for(paid_storage, project, billing_user)

    assert "apply_no_cost_quota" not in form.fields
    assert {"cost_center", "grant"} <= set(form.fields)  # still asked


def test_a_grant_needs_a_cost_center(project, pi_user, paid_storage, grant_center):
    form = form_for(paid_storage, project, pi_user, {f"{BILLING_SECTION_NAME}-grant": grant_center.name})

    assert not form.is_valid()
    assert "grant" in form.errors


# -- Saving -----------------------------------------------------------------------------------------


def make_allocation(project, resource, allocation_status_new):
    allocation = Allocation.objects.create(project=project, status=allocation_status_new, justification="x")
    allocation.resources.add(resource)
    return allocation


def test_saving_assigns_the_project_to_the_cost_center_and_grant(
    project, pi_user, paid_storage, cost_center, grant_center, allocation_status_new
):
    section = section_for(paid_storage, project, pi_user)
    form = section.build_form(
        {f"{BILLING_SECTION_NAME}-cost_center": cost_center.name, f"{BILLING_SECTION_NAME}-grant": grant_center.name}
    )
    assert form.is_valid(), form.errors

    section.save(make_allocation(project, paid_storage, allocation_status_new), form)

    assignment = CostCenterAssignment.objects.get(project=project)
    assert assignment.assignments == [{"department": cost_center.name, "percentage": 100, "grant": grant_center.name}]


def test_saving_without_a_cost_center_assigns_nothing(project, pi_user, paid_storage, allocation_status_new):
    section = section_for(paid_storage, project, pi_user)
    form = section.build_form({})
    assert form.is_valid(), form.errors

    section.save(make_allocation(project, paid_storage, allocation_status_new), form)

    assert not CostCenterAssignment.objects.filter(project=project).exists()


@pytest.mark.parametrize("apply", [True, False])
def test_saving_records_the_no_cost_quota_to_apply_at_activation(
    project, billing_user, paid_storage, no_cost_quota, allocation_status_new, apply
):
    section = section_for(paid_storage, project, billing_user)
    form = section.build_form({f"{BILLING_SECTION_NAME}-apply_no_cost_quota": "on"} if apply else {})
    assert form.is_valid(), form.errors
    allocation = make_allocation(project, paid_storage, allocation_status_new)

    section.save(allocation, form)

    recorded = allocation.get_attribute(ALLOCATION_QUOTA_ATTRIBUTE_NAME, expand=False, typed=False)
    assert recorded == (str(no_cost_quota.pk) if apply else None)


# -- On the request page ----------------------------------------------------------------------------


@pytest.fixture
def requesting_pi(client, project, pi_user, manager_role, project_user_status_active):
    """The PI, signed in, and allowed the project's request page: ColdFront grants it to Managers."""
    ProjectUser.objects.create(project=project, user=pi_user, role=manager_role, status=project_user_status_active)
    AllocationStatusChoice.objects.get_or_create(name="New")
    AllocationUserStatusChoice.objects.get_or_create(name="Active")
    client.force_login(pi_user)
    return pi_user


def test_the_request_page_shows_the_card(client, requesting_pi, project, paid_storage):
    response = request_cards(client, project, paid_storage)

    assert f'data-request-section="{BILLING_SECTION_NAME}"' in response.content.decode()


def test_a_request_with_a_cost_center_is_complete_when_submitted(
    client, requesting_pi, project, paid_storage, cost_center
):
    data = {
        "resource": str(paid_storage.pk),
        "justification": "Sequencing data for the NIH R01 project.",
        "quantity": "1",
        "project": str(project.pk),
        "is_changeable": "True",
        f"{BILLING_SECTION_NAME}-cost_center": cost_center.name,
        QUOTA_FIELD_NAME: "10",  # the storage quota card's field
    }

    response = client.post(reverse("allocation-create", args=[project.pk]), data)

    assert response.status_code == 302 and "update-allocation-details" not in response.url
    assert Allocation.objects.filter(project=project).exists()
    assert CostCenterAssignment.objects.get(project=project).assignments[0]["department"] == cost_center.name


# -- The old second page is gone ------------------------------------------------------------------


def test_billing_no_longer_replaces_the_request_view():
    assert allocation_views.AllocationCreateView is AllocationRequestCreateView


@pytest.mark.parametrize("name", ["update_allocation_details", "delete_incomplete_allocation"])
def test_the_old_quota_page_and_its_cancel_are_gone(name):
    with pytest.raises(NoReverseMatch):
        reverse(name, args=[1])


def test_the_change_requests_cost_preview_stays():
    assert reverse("allocation_cost_preview", args=[1])


# -- The check: the section needs the app -----------------------------------------------------------


def test_the_check_passes_with_the_request_form_app_installed():
    assert billing_checks.check_allocation_request_app(None) == []


def test_the_check_fails_without_the_request_form_app(monkeypatch):
    real_is_installed = global_apps.is_installed

    def without_request_app(app_name):
        return app_name != "coldfront_utils.allocation_request" and real_is_installed(app_name)

    monkeypatch.setattr(global_apps, "is_installed", without_request_app)

    [error] = billing_checks.check_allocation_request_app(None)

    assert error.id == "coldfront_billing.E001"


# -- The cost estimate ------------------------------------------------------------------------------


@pytest.fixture
def priced_storage(paid_storage, cost_attribute_type):
    """paid_storage at $100 per TB a month."""
    ResourceAttribute.objects.create(resource=paid_storage, resource_attribute_type=cost_attribute_type, value="100")
    return paid_storage


def estimate(client, project, resource, quota):
    return client.get(
        reverse("request_cost_estimate", args=[project.pk]), {"resource": resource.pk, QUOTA_FIELD_NAME: quota}
    )


def test_the_quota_field_id_is_djangos_for_its_name():
    assert (QUOTA_FIELD_NAME, QUOTA_FIELD_ID) == ("storage_quota-quota", "id_storage_quota-quota")


def test_the_storage_card_asks_for_the_estimate_as_the_quota_changes(client, requesting_pi, project, priced_storage):
    html = request_cards(client, project, priced_storage).content.decode()

    assert reverse("request_cost_estimate", args=[project.pk]) in html
    assert f"from:#{QUOTA_FIELD_ID}" in html and f'hx-include="#{QUOTA_FIELD_ID}"' in html


def test_a_card_for_a_resource_that_isnt_storage_has_no_estimate(client, requesting_pi, project, billed_compute):
    html = request_cards(client, project, billed_compute).content.decode()

    assert f'data-request-section="{BILLING_SECTION_NAME}"' in html
    assert "request_cost_estimate" not in html and "cost-estimate" not in html


@pytest.mark.parametrize("why", ["not registered", "set not to ask"])
def test_a_card_without_the_quota_card_has_no_estimate(
    client, requesting_pi, project, priced_storage, monkeypatch, why
):
    """There's no quota field for it to read."""
    if why == "not registered":
        without_the_quota_card(monkeypatch)
    else:
        set_not_to_ask_for_a_quota(priced_storage)

    html = request_cards(client, project, priced_storage).content.decode()

    assert f'data-request-section="{BILLING_SECTION_NAME}"' in html
    assert "cost-estimate" not in html


def test_the_estimate_is_the_quota_times_the_price(client, requesting_pi, project, priced_storage):
    html = estimate(client, project, priced_storage, "2.5").content.decode()

    assert "$250.00" in html and "$100.00" in html
    assert "no-cost" not in html  # the requester has none


def test_a_large_quota_is_priced_too(client, requesting_pi, project, priced_storage):
    # the quota field's own limit is storage's; the estimate prices whatever billing can
    assert "$100000000.00" in estimate(client, project, priced_storage, "1000000").content.decode()


def test_the_estimate_writes_the_quota_out(client, requesting_pi, project, priced_storage):
    assert "1000 TB" in estimate(client, project, priced_storage, "1e3").content.decode()


def test_the_estimate_shows_the_cost_with_the_no_cost_quota(
    client, requesting_pi, project, priced_storage, no_cost_quota
):
    no_cost_quota.user = requesting_pi
    no_cost_quota.save()

    html = estimate(client, project, priced_storage, "150").content.decode()

    assert "$15000.00" in html  # without it
    assert "$5000.00" in html and "100" in html  # with 100 TB at no cost


@pytest.mark.parametrize("quota", ["", "abc", "-1", "1e30"])
def test_without_a_usable_quota_the_estimate_asks_for_one(client, requesting_pi, project, priced_storage, quota):
    response = estimate(client, project, priced_storage, quota)

    assert response.status_code == 200 and "$" not in response.content.decode()


@pytest.mark.parametrize("resource", ["abc", "", "999"])
def test_a_resource_that_isnt_one_is_not_found(client, requesting_pi, project, resource):
    response = client.get(
        reverse("request_cost_estimate", args=[project.pk]), {"resource": resource, QUOTA_FIELD_NAME: "1"}
    )

    assert response.status_code == 404


def test_the_estimate_needs_the_request_pages_permission(client, project, priced_storage, user):
    client.force_login(user)

    assert estimate(client, project, priced_storage, "1").status_code == 403


def test_the_estimate_is_only_for_paid_storage(client, requesting_pi, project, billed_compute, storage_resource_type):
    free = Resource.objects.create(resource_type=storage_resource_type, name="Course", requires_payment=False)

    assert estimate(client, project, billed_compute, "1").status_code == 404
    assert estimate(client, project, free, "1").status_code == 404
