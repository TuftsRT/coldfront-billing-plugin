from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from coldfront.core.allocation.models import (
    AllocationAttribute,
    AllocationAttributeType,
)
from coldfront.core.allocation.models import (
    AttributeType as AllocationAttributeTypeBase,
)

from coldfront_billing.models import CostCenterAssignment
from coldfront_billing.reports.billing_preview import (
    get_all_storage_allocations,
    get_cost_per_allocation,
    get_cost_previews,
    missing_billing_code_report,
)
from coldfront_billing.tests.conftest import add_storage_allocation_to_project

User = get_user_model()


@pytest.mark.django_db
class TestBillingPreviewReports:
    def test_missing_billing_code_report_includes_projects_without_cost_center_assignment(
        self,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            cost_value="25",
            quota_value="10",
            resource_name="Preview Storage",
        )

        result = missing_billing_code_report()

        assert result["month"]
        assert result["total_cost"] == pytest.approx(250.0)
        assert len(result["missing_billing_code"]) == 1
        assert result["missing_billing_code"][0]["project"] == project
        assert result["missing_billing_code"][0]["project_cost"] == pytest.approx(250.0)

    def test_missing_billing_code_report_includes_projects_with_empty_cost_center_assignments(
        self,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            cost_value="18",
            quota_value="9",
            resource_name="Empty Assignment Preview Storage",
        )
        CostCenterAssignment.objects.create(project=project, assignments=[])

        result = missing_billing_code_report()

        assert result["total_cost"] == Decimal("162.00")
        assert len(result["missing_billing_code"]) == 1
        assert result["missing_billing_code"][0]["project"] == project
        assert result["missing_billing_code"][0]["project_cost"] == Decimal("162.00")

    def test_missing_billing_code_report_with_no_username_match_returns_empty_result(
        self,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            cost_value="12",
            quota_value="6",
            resource_name="No Match Preview Storage",
        )

        result = missing_billing_code_report(username="definitely-no-match")

        assert result["missing_billing_code"] == []
        assert result["total_cost"] == Decimal("0.00")
        assert result["month"]

    def test_get_cost_previews_with_no_username_match_returns_empty_result(
        self,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            cost_value="20",
            quota_value="10",
            resource_name="No Username Match Storage",
        )
        CostCenterAssignment.objects.create(
            project=project,
            assignments=[{"department": "DEPT001", "percentage": 100}],
        )

        result = get_cost_previews(username="definitely-no-match", username_exact=True)

        assert result["charge_report"] == []
        assert result["missing_billing_code"] == []
        assert result["total_cost"] == Decimal("0.00")
        assert result["month"]

    def test_get_cost_previews_with_no_billing_code_match_returns_empty_result(
        self,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            cost_value="20",
            quota_value="10",
            resource_name="No Billing Code Match Storage",
        )
        CostCenterAssignment.objects.create(
            project=project,
            assignments=[{"department": "DEPT001", "percentage": 100}],
        )

        result = get_cost_previews(billing_code="NO_SUCH_DEPT", username_exact=True)

        assert result["charge_report"] == []
        assert result["missing_billing_code"] == []
        assert result["total_cost"] == Decimal("0.00")
        assert result["month"]

    def test_get_cost_previews_filters_by_username_and_billing_code(
        self,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            cost_value="20",
            quota_value="10",
            resource_name="Charge Storage",
        )
        CostCenterAssignment.objects.create(
            project=project,
            assignments=[
                {"department": "DEPT001", "percentage": 60},
                {"department": "DEPT002", "percentage": 40},
            ],
        )

        result = get_cost_previews(username=project.pi.username, billing_code="DEPT001", username_exact=True)

        assert result["total_cost"] == pytest.approx(200.0)
        assert len(result["charge_report"]) == 2
        cost_by_department = {row["department"]: row["charged_to_id"] for row in result["charge_report"]}
        assert set(cost_by_department) == {"DEPT001", "DEPT002"}
        assert cost_by_department["DEPT001"] == Decimal("120.00")
        assert cost_by_department["DEPT002"] == Decimal("80.01")
        assert result["total_cost"] == Decimal("200.00")
        assert result["missing_billing_code"] == []

    def test_get_cost_previews_reports_projects_without_cost_center_assignment(
        self,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            cost_value="15",
            quota_value="8",
            resource_name="Missing Dept Storage",
        )

        result = get_cost_previews(username=project.pi.username, username_exact=True)

        assert result["total_cost"] == pytest.approx(120.0)
        assert len(result["missing_billing_code"]) == 1
        assert result["missing_billing_code"][0]["project"] == project
        assert result["charge_report"] == []

    def test_get_cost_per_allocation_aggregates_allocations_and_ncq(
        self,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        allocation, storage_resource = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            cost_value="30",
            quota_value="10",
            resource_name="Per Allocation Storage",
        )
        text_attr_type, _ = AllocationAttributeTypeBase.objects.get_or_create(name="Text")
        sf_vol_path_type, _ = AllocationAttributeType.objects.get_or_create(
            name="sf_vol_path",
            defaults={"attribute_type": text_attr_type},
        )
        AllocationAttribute.objects.create(
            allocation=allocation,
            allocation_attribute_type=sf_vol_path_type,
            value="/mnt/per-allocation",
        )

        rows = get_cost_per_allocation()

        assert len(rows) == 1
        row = rows[0]
        assert row["owner"] == project.pi.username
        assert row["resource"] == storage_resource.name
        assert row["vol_path"] == "/mnt/per-allocation"
        assert row["quota_tb"] == Decimal("10")
        assert row["cost_per_tb"] == Decimal("30")
        assert row["cost"] == Decimal("300.00")
        assert row["ncq_applied"] == Decimal("0")
        assert row["cost_after_ncq"] == pytest.approx(300.0)

    def test_get_all_storage_allocations_returns_storage_row_for_each_allocation(
        self,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        allocation, storage_resource = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            cost_value="25",
            quota_value="5",
            resource_name="Storage Row Resource",
        )
        text_attr_type, _ = AllocationAttributeTypeBase.objects.get_or_create(name="Text")
        sf_vol_path_type, _ = AllocationAttributeType.objects.get_or_create(
            name="sf_vol_path",
            defaults={"attribute_type": text_attr_type},
        )
        quota_type, _ = AllocationAttributeType.objects.get_or_create(
            name="reported_quota_bytes",
            defaults={"attribute_type": text_attr_type},
        )
        usage_type, _ = AllocationAttributeType.objects.get_or_create(
            name="reported_usage_bytes",
            defaults={"attribute_type": text_attr_type},
        )

        AllocationAttribute.objects.create(
            allocation=allocation,
            allocation_attribute_type=sf_vol_path_type,
            value="/mnt/project-data",
        )
        AllocationAttribute.objects.create(
            allocation=allocation,
            allocation_attribute_type=quota_type,
            value="5000000000000",
        )
        AllocationAttribute.objects.create(
            allocation=allocation,
            allocation_attribute_type=usage_type,
            value="2500000000000",
        )

        rows = get_all_storage_allocations()

        assert len(rows) == 1
        row = rows[0]
        assert row["owner"] == project.pi.username
        assert row["resource"] == storage_resource.name
        assert row["vol_path"] == "/mnt/project-data"
        assert row["requires_payment"] is True
        assert row["status"] == allocation_status_active.name
        assert row["quota"] == Decimal("5.00")
        assert row["usage"] == Decimal("2.5000")
        assert row["ncq_owner"] is None
        assert row["ncq_amount"] is None
        assert row["ncq_quota_type"] is None
