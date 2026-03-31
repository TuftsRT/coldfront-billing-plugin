from unittest.mock import Mock

from coldfront_billing.data import BillingAllocation, BillingQuota
from coldfront_billing.enum import StorageUnit

from .allocation_mocks import (
    create_mock_allocation,
    create_mock_allotment,
    create_mock_storage_resource,
)
from .defaults import DEFAULT_COST, DEFAULT_QUOTA


class TestBillingAllocationNoCostQuotas:
    """Test suite for BillingAllocation no_cost_quotas functionality."""

    def test_total_cost_reduced_by_no_cost_quota_tb(self):
        """Test total_cost is reduced when no_cost_quotas (TB) are present."""
        billing = BillingAllocation(
            allocation_id=1,
            project_id=1,
            quota_tb=10,
            cost_per_tb=100,
            no_cost_quotas=[BillingQuota(amount=3.0, unit=StorageUnit.TB)],
        )
        # 10 - 3 = 7 TB billable, ceil(7) * 100 = 700
        assert billing.total_cost == 700

    def test_total_cost_reduced_by_no_cost_quota_gb(self):
        """Test total_cost is reduced when no_cost_quotas (GB) are present."""
        billing = BillingAllocation(
            allocation_id=1,
            project_id=1,
            quota_tb=5,
            cost_per_tb=100,
            no_cost_quotas=[BillingQuota(amount=1000.0, unit=StorageUnit.GB)],
        )
        # 5 - 1 = 4 TB billable, 4 * 100 = 400
        assert billing.total_cost == 400

    def test_total_cost_with_multiple_no_cost_quotas(self):
        """Test total_cost with multiple no_cost_quotas summed."""
        billing = BillingAllocation(
            allocation_id=1,
            project_id=1,
            quota_tb=10,
            cost_per_tb=100,
            no_cost_quotas=[
                BillingQuota(amount=2.0, unit=StorageUnit.TB),
                BillingQuota(amount=500.0, unit=StorageUnit.GB),  # 0.5 TB
            ],
        )
        # 10 - 2.5 = 7.5 TB billable, ceil(7.5) * 100 = 800
        assert billing.total_cost == 800

    def test_total_cost_no_cost_quota_exceeds_quota_returns_zero(self):
        """Test total_cost is zero when no_cost_quotas exceed quota."""
        billing = BillingAllocation(
            allocation_id=1,
            project_id=1,
            quota_tb=5,
            cost_per_tb=100,
            no_cost_quotas=[BillingQuota(amount=10.0, unit=StorageUnit.TB)],
        )
        # max(5 - 10, 0) = 0, 0 * 100 = 0
        assert billing.total_cost == 0

    def test_total_cost_empty_no_cost_quotas_unchanged(self):
        """Test total_cost with empty no_cost_quotas behaves like before."""
        billing = BillingAllocation(
            allocation_id=1,
            project_id=1,
            quota_tb=5,
            cost_per_tb=100,
            no_cost_quotas=[],
        )
        assert billing.total_cost == 500

    def test_parse_with_no_cost_quota_data(self):
        """Test parse populates no_cost_quotas from allocation allotments."""
        allotment1 = create_mock_allotment(amount=2.0, units='TB')
        allotment2 = create_mock_allotment(amount=500.0, units='GB')
        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='10')],
            storage_resources=[storage_resource],
            no_cost_quota_data=[allotment1, allotment2],
        )

        result = BillingAllocation.parse(allocation, DEFAULT_QUOTA, DEFAULT_COST)

        assert len(result.no_cost_quotas) == 2
        assert result.no_cost_quotas[0].amount == 2.0
        assert result.no_cost_quotas[0].unit == StorageUnit.TB
        assert result.no_cost_quotas[1].amount == 500.0
        assert result.no_cost_quotas[1].unit == StorageUnit.GB
        assert result.total_cost == 800  # 10 - 2.5 = 7.5 TB, ceil(7.5) * 100 = 800

    def test_parse_without_no_cost_quota_data_yields_empty(self):
        """Test parse when allocation has no allotments (attribute not set, real-life scenario)."""
        storage_resource = create_mock_storage_resource(cost_attrs=[Mock(value='100')])
        allocation = create_mock_allocation(
            quota_attrs=[Mock(value='5')],
            storage_resources=[storage_resource],
        )

        result = BillingAllocation.parse(allocation, DEFAULT_QUOTA, DEFAULT_COST)

        assert result.no_cost_quotas == []
        assert result.total_cost == 500
