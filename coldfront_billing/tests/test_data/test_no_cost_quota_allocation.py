from unittest.mock import Mock

from coldfront_billing.constants import ALLOTMENTS_ATTRIBUTE_NAME, QUOTA_ATTRIBUTE_NAME
from coldfront_billing.data import BillingQuota, NoCostQuotaAllocation
from coldfront_billing.enum import StorageUnit


class TestNoCostQuotaAllocation:
    """Test suite for NoCostQuotaAllocation class."""

    @staticmethod
    def _create_mock_allotment(amount, units='TB', user_id=1):
        """Helper to create a mock allotment for NoCostQuotaAllocation.create()."""
        allotment = Mock()
        allotment.amount = amount
        allotment.no_cost_quota = Mock()
        allotment.no_cost_quota.units = units
        allotment.no_cost_quota.user_id = user_id
        return allotment

    @staticmethod
    def _create_mock_allocation_for_create(all_allotments=(), quota_attrs=None):
        """Build a mock allocation like the assign view: all_allotments + prefetched quota_attr."""
        allocation = Mock(spec=['id', ALLOTMENTS_ATTRIBUTE_NAME, QUOTA_ATTRIBUTE_NAME])
        allocation.id = 1
        allocation.all_allotments = all_allotments
        if quota_attrs is not None:
            setattr(allocation, QUOTA_ATTRIBUTE_NAME, quota_attrs)
        else:
            setattr(allocation, QUOTA_ATTRIBUTE_NAME, [Mock(value='10')])
        return allocation

    def test_user_amount_with_users_allotment(self):
        """Test user_amount returns the amount when users_allotment is set."""
        users_allotment = BillingQuota(amount=5.0, unit=StorageUnit.TB)
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=10.0,
            users_allotment=users_allotment,
            other_allotments=[],
        )
        assert allocation.user_amount == 5.0

    def test_user_amount_without_users_allotment(self):
        """Test user_amount returns 0 when users_allotment is None."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=10.0,
            users_allotment=None,
            other_allotments=[],
        )
        assert allocation.user_amount == 0

    def test_user_allotment_amount_with_users_allotment_tb(self):
        """Test user_allotment_amount returns normalized TB amount."""
        users_allotment = BillingQuota(amount=3.0, unit=StorageUnit.TB)
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=10.0,
            users_allotment=users_allotment,
            other_allotments=[],
        )
        assert allocation.user_allotment_amount == 3.0

    def test_user_allotment_amount_with_users_allotment_gb(self):
        """Test user_allotment_amount returns normalized amount for GB (converts to TB)."""
        users_allotment = BillingQuota(amount=1000.0, unit=StorageUnit.GB)
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=10.0,
            users_allotment=users_allotment,
            other_allotments=[],
        )
        assert allocation.user_allotment_amount == 1.0

    def test_user_allotment_amount_without_users_allotment(self):
        """Test user_allotment_amount returns 0 when users_allotment is None."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=10.0,
            users_allotment=None,
            other_allotments=[],
        )
        assert allocation.user_allotment_amount == 0

    def test_other_allotments_amount_empty(self):
        """Test other_allotments_amount returns 0 when no other allotments."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=10.0,
            users_allotment=BillingQuota(amount=2.0, unit=StorageUnit.TB),
            other_allotments=[],
        )
        assert allocation.other_allotments_amount == 0

    def test_other_allotments_amount_single(self):
        """Test other_allotments_amount sums single allotment."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=10.0,
            users_allotment=None,
            other_allotments=[BillingQuota(amount=3.0, unit=StorageUnit.TB)],
        )
        assert allocation.other_allotments_amount == 3.0

    def test_other_allotments_amount_multiple_mixed_units(self):
        """Test other_allotments_amount sums multiple allotments with mixed units."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=10.0,
            users_allotment=None,
            other_allotments=[
                BillingQuota(amount=2.0, unit=StorageUnit.TB),
                BillingQuota(amount=1000.0, unit=StorageUnit.GB),  # 1 TB
            ],
        )
        assert allocation.other_allotments_amount == 3.0

    def test_max_possible_allocation_allocation_amount_none(self):
        """Test max_possible_allocation when allocation_amount is None returns remaining + user allotment."""
        users_allotment = BillingQuota(amount=2.0, unit=StorageUnit.TB)
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=None,
            users_allotment=users_allotment,
            other_allotments=[],
        )
        result = allocation.max_possible_allocation(remaining_quota=5.0, quota_unit='TB', min_increment=1.0)
        assert result == 7.0  # 5 + 2

    def test_max_possible_allocation_limit_from_quota(self):
        """Test max_possible_allocation when allocation_amount is set and limits result."""
        users_allotment = BillingQuota(amount=1.0, unit=StorageUnit.TB)
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=10.0,
            users_allotment=users_allotment,
            other_allotments=[
                BillingQuota(amount=2.0, unit=StorageUnit.TB),
                BillingQuota(amount=1000.0, unit=StorageUnit.GB),  # 1 TB
            ],
        )
        # remaining_quota=5 + 1 (existing user_allotment) = 6 TB possible from quota
        # allocation_available = 10 - 3 (from other users) = 7 TB
        # min(6, 7) = 6, floor(6/1)*1 = 6
        result = allocation.max_possible_allocation(remaining_quota=5.0, quota_unit='TB', min_increment=1.0)
        assert result == 6.0

    def test_max_possible_allocation_limit_from_allocation(self):
        """Test max_possible_allocation when allocation limit is lower than quota."""
        users_allotment = BillingQuota(amount=5.0, unit=StorageUnit.TB)
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=8.0,
            users_allotment=users_allotment,
            other_allotments=[BillingQuota(amount=6.0, unit=StorageUnit.TB)],
        )
        # remaining_quota=10 + 5 (existing user_allotment) = 15 TB
        # allocation_available = 8 - 6 = 2 TB
        # min(15, 2) = 2, floor(2/1)*1 = 2
        result = allocation.max_possible_allocation(remaining_quota=10.0, quota_unit='TB', min_increment=1.0)
        assert result == 2.0

    def test_max_possible_allocation_allocation_amount_none_rounds_to_two_decimals(self):
        """Test max_possible_allocation when allocation_amount is None rounds to 2 decimal places."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=None,
            users_allotment=BillingQuota(amount=1.333, unit=StorageUnit.TB),
            other_allotments=[],
        )
        result = allocation.max_possible_allocation(remaining_quota=2.666, quota_unit='TB', min_increment=0.1)
        assert result == 4.0  # 2.666 + 1.333 = 3.999 -> round(4.0, 2) = 4.0

    def test_max_possible_allocation_floors_to_min_increment(self):
        """Test max_possible_allocation floors result to nearest min_increment when allocation_amount is set."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=5.0,
            users_allotment=None,
            other_allotments=[BillingQuota(amount=2.0, unit=StorageUnit.TB)],
        )
        # allocation_available = 5 - 2 = 3 TB, remaining_quota=2.95 -> max_possible = min(2.95, 3) = 2.95
        # floor(2.95 / 0.1) * 0.1 = 2.9
        result = allocation.max_possible_allocation(remaining_quota=2.95, quota_unit='TB', min_increment=0.1)
        assert result == 2.9

    def test_max_possible_allocation_other_allotments_exceed_allocation(self):
        """Test max_possible_allocation when other allotments exceed allocation_amount."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=5.0,
            users_allotment=None,
            other_allotments=[BillingQuota(amount=10.0, unit=StorageUnit.TB)],
        )
        # allocation_available_tb = max(0, 5 - 10) = 0
        result = allocation.max_possible_allocation(remaining_quota=5.0, quota_unit='TB', min_increment=1.0)
        assert result == 0.0

    def test_max_possible_allocation_quota_unit_gb(self):
        """Test max_possible_allocation with GB quota unit."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=1.0,  # 1 TB
            users_allotment=None,
            other_allotments=[],
        )
        # allocation_available = 1 TB = 1000 GB, min(500, 1000) = 500
        result = allocation.max_possible_allocation(remaining_quota=500.0, quota_unit='GB', min_increment=1.0)
        assert result == 500.0

    def test_max_possible_allocation_remaining_gb_limited_by_allocation_tb_cap(self):
        """Remaining quota in GB cannot exceed allocation headroom converted to GB."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=2.0,  # 2 TB free before other allotments
            users_allotment=None,
            other_allotments=[],
        )
        # 2 TB -> 2000 GB capacity; remaining 3500 GB -> assign 2000 GB
        result = allocation.max_possible_allocation(remaining_quota=3500.0, quota_unit='GB', min_increment=1.0)
        assert result == 2000.0

    def test_max_possible_allocation_remaining_gb_adds_user_allotment_raw_gb(self):
        """With quota_unit GB, user_amount is raw allotment amount (use GB-stored allotment for consistency)."""
        users_allotment = BillingQuota(amount=100.0, unit=StorageUnit.GB)
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=1.0,  # 1 TB = 1000 GB on allocation
            users_allotment=users_allotment,
            other_allotments=[],
        )
        # possible_quota = 400 + 100 = 500 GB; cap 1000 GB -> 500 GB
        result = allocation.max_possible_allocation(remaining_quota=400.0, quota_unit='GB', min_increment=1.0)
        assert result == 500.0

    def test_max_possible_allocation_remaining_gb_floors_to_min_increment(self):
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=1.0,  # 1000 GB
            users_allotment=None,
            other_allotments=[],
        )
        result = allocation.max_possible_allocation(remaining_quota=955.0, quota_unit='GB', min_increment=100.0)
        assert result == 900.0

    def test_max_possible_allocation_remaining_gb_other_allotments_tb_reduce_headroom(self):
        """Other users' allotments stored in TB reduce TB cap before headroom is converted to GB."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=6.0,
            users_allotment=None,
            other_allotments=[BillingQuota(amount=2.5, unit=StorageUnit.TB)],
        )
        # 6 - 2.5 = 3.5 TB -> 3500 GB; remaining 5000 GB -> min = 3500 GB
        result = allocation.max_possible_allocation(5000.0, quota_unit='GB', min_increment=1.0)
        assert result == 3500.0

    def test_max_possible_allocation_remaining_gb_multiple_other_allotments_tb(self):
        """Several TB other allotments sum in TB (normalized) then subtract from allocation cap."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=8.0,
            users_allotment=None,
            other_allotments=[
                BillingQuota(amount=1.0, unit=StorageUnit.TB),
                BillingQuota(amount=2.0, unit=StorageUnit.TB),
            ],
        )
        # 8 - 3 = 5 TB = 5000 GB
        result = allocation.max_possible_allocation(10000.0, quota_unit='GB', min_increment=1.0)
        assert result == 5000.0

    def test_max_possible_allocation_remaining_gb_other_tb_fills_allocation_returns_zero(self):
        """When TB others use the full allocation TB, no GB can be assigned."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=4.0,
            users_allotment=None,
            other_allotments=[BillingQuota(amount=4.0, unit=StorageUnit.TB)],
        )
        result = allocation.max_possible_allocation(2000.0, quota_unit='GB', min_increment=1.0)
        assert result == 0.0

    def test_max_possible_allocation_remaining_gb_with_user_gb_and_other_tb(self):
        """GB remaining + user raw GB amount, capped by (allocation TB - other TB) converted to GB."""
        users_allotment = BillingQuota(amount=50.0, unit=StorageUnit.GB)
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=2.0,
            users_allotment=users_allotment,
            other_allotments=[BillingQuota(amount=0.5, unit=StorageUnit.TB)],
        )
        # Headroom 1.5 TB = 1500 GB; possible_quota = 200 + 50 = 250 GB
        result = allocation.max_possible_allocation(200.0, quota_unit='GB', min_increment=1.0)
        assert result == 250.0

    def test_max_possible_allocation_allocation_amount_none_remaining_gb_rounds(self):
        """No allocation TB cap: possible quota is remaining + user_amount in quota units (GB + raw user amount)."""
        allocation = NoCostQuotaAllocation(
            user_id=1,
            allocation_amount=None,
            users_allotment=None,
            other_allotments=[],
        )
        result = allocation.max_possible_allocation(remaining_quota=1234.567, quota_unit='GB', min_increment=1.0)
        assert result == 1234.57

    def test_create_with_user_in_allotments(self):
        """Test create extracts user allotment for matching user_id."""
        allotments = [
            self._create_mock_allotment(amount=2.0, units='TB', user_id=1),
            self._create_mock_allotment(amount=3.0, units='TB', user_id=2),
        ]
        allocation = self._create_mock_allocation_for_create(all_allotments=allotments, quota_attrs=[Mock(value='10')])
        result = NoCostQuotaAllocation.create(1, allocation)

        assert result.user_id == 1
        assert result.allocation_amount == 10.0
        assert result.users_allotment is not None
        assert result.users_allotment.amount == 2.0
        assert result.users_allotment.unit == StorageUnit.TB
        assert len(result.other_allotments) == 1
        assert result.other_allotments[0].amount == 3.0

    def test_create_without_user_in_allotments(self):
        """Test create sets users_allotment to None when user not in allotments."""
        allotments = [
            self._create_mock_allotment(amount=2.0, units='TB', user_id=2),
            self._create_mock_allotment(amount=3.0, units='TB', user_id=3),
        ]
        allocation = self._create_mock_allocation_for_create(all_allotments=allotments, quota_attrs=[Mock(value='10')])
        result = NoCostQuotaAllocation.create(1, allocation)

        assert result.users_allotment is None
        assert len(result.other_allotments) == 2

    def test_create_with_empty_allotments(self):
        """Test create with empty allotments."""
        allocation = self._create_mock_allocation_for_create(all_allotments=[], quota_attrs=[Mock(value='10')])
        result = NoCostQuotaAllocation.create(1, allocation)

        assert result.users_allotment is None
        assert result.other_allotments == []

    def test_create_with_gb_units(self):
        """Test create correctly parses GB units."""
        allotments = [
            self._create_mock_allotment(amount=1000.0, units='GB', user_id=1),
        ]
        allocation = self._create_mock_allocation_for_create(all_allotments=allotments, quota_attrs=[Mock(value='5')])
        result = NoCostQuotaAllocation.create(1, allocation)

        assert result.users_allotment.amount == 1000.0
        assert result.users_allotment.unit == StorageUnit.GB
        assert result.users_allotment.normalized_amount == 1.0
        assert result.allocation_amount == 5.0

    def test_create_without_quota_attribute_sets_allocation_amount_none(self):
        """Test create sets allocation_amount to None when quota prefetch is missing or empty."""
        allocation = self._create_mock_allocation_for_create(all_allotments=[], quota_attrs=[])
        result = NoCostQuotaAllocation.create(1, allocation)
        assert result.allocation_amount is None

    def test_create_invalid_quota_value_sets_allocation_amount_none(self):
        """Test create sets allocation_amount to None when quota value is not a float."""
        allocation = self._create_mock_allocation_for_create(
            all_allotments=[], quota_attrs=[Mock(value='not-a-number')]
        )
        result = NoCostQuotaAllocation.create(1, allocation)
        assert result.allocation_amount is None
