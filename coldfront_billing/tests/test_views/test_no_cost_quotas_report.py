"""Tests for the no-cost-quotas report's JSON export."""

from decimal import Decimal

import pytest
from django.urls import reverse

from coldfront.core.allocation.models import AllocationAttribute, AllocationAttributeType
from coldfront.core.allocation.models import AttributeType as AllocationAttributeTypeBase

from coldfront_billing.models import NoCostQuotaAllotment
from coldfront_billing.tests.conftest import add_storage_allocation_to_project


def _add_report_attributes(allocation, vol_path="/storage/lab", usage_bytes="3000000000000"):
    text_type, _ = AllocationAttributeTypeBase.objects.get_or_create(name="Text")
    for name, value in (("sf_vol_path", vol_path), ("reported_usage_bytes", usage_bytes)):
        attribute_type, _ = AllocationAttributeType.objects.get_or_create(
            name=name, defaults={"attribute_type": text_type}
        )
        AllocationAttribute.objects.create(allocation=allocation, allocation_attribute_type=attribute_type, value=value)


@pytest.mark.django_db
@pytest.mark.usefixtures("configure_urls")
class TestNoCostQuotasReportJson:
    def test_superuser_json_format_returns_serialized_payload(
        self,
        client,
        superuser,
        project,
        no_cost_quota,
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
        )
        _add_report_attributes(allocation)
        NoCostQuotaAllotment.objects.create(
            no_cost_quota=no_cost_quota, allocation=allocation, amount_tb=Decimal("1.000")
        )

        client.force_login(superuser)
        response = client.get(reverse("no-cost-quotas-report"), {"format": "json"})

        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"
        payload = response.json()
        assert payload["errors"] == []
        assert payload["shared_allotments"] == []
        [row] = payload["allocations"]
        assert row["allocation_id"] == allocation.id
        assert row["project_id"] == project.id
        assert row["project_title"] == project.title
        assert row["storage_owner"] == project.pi.username
        assert row["vol_path"] == "/storage/lab"
        assert row["quota"] == "3.00000"
        assert row["ncq_allot_total"] == "1.000"
        assert row["billable_quota"] == "2.00000"
        assert row["allotments"] == [
            {"amount": "1.000", "quota_type": "tier_1", "ncq_owner": no_cost_quota.user.username}
        ]
        assert "allocation" not in row

    def test_superuser_json_format_with_no_results(self, client, superuser, storage_resource_type):
        client.force_login(superuser)
        response = client.get(reverse("no-cost-quotas-report"), {"format": "json"})

        assert response.status_code == 200
        assert response.json() == {"allocations": [], "shared_allotments": [], "errors": []}
