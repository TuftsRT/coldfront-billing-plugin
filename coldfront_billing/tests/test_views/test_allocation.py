"""Unit tests for AllocationCostPreviewView, the cost estimate of a change request."""

import pytest
from django.urls import reverse

from coldfront_billing.tests.conftest import add_storage_allocation_to_project


@pytest.mark.django_db
@pytest.mark.usefixtures("configure_urls")
class TestAllocationCostPreviewView:
    @staticmethod
    def _preview(client, user, allocation_pk, quota_tb):
        client.force_login(user)
        url = reverse("allocation_cost_preview", kwargs={"pk": allocation_pk})
        return client.get(url, {"quota_in_terabyte": quota_tb})

    def test_missing_quota_parameter_returns_400(
        self,
        client,
        superuser,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        allocation, _ = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            with_quota=False,
        )
        client.force_login(superuser)
        response = client.get(reverse("allocation_cost_preview", kwargs={"pk": allocation.pk}))
        assert response.status_code == 400
        assert "quota_in_terabyte" in response.json()["error"]

    def test_negative_quota_returns_400(
        self,
        client,
        superuser,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        allocation, _ = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            with_quota=False,
        )
        response = self._preview(client, superuser, allocation.pk, "-1")
        assert response.status_code == 400

    def test_returns_cost_breakdown(
        self,
        client,
        superuser,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        allocation, _ = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            with_quota=False,
            cost_value="100",
        )
        response = self._preview(client, superuser, allocation.pk, "10")
        assert response.status_code == 200
        data = response.json()
        assert data["quota_tb"] == "10"
        assert data["cost_per_tb"] == "100"
        assert "total_cost" in data
