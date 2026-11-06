from decimal import Decimal
from unittest.mock import Mock

from coldfront_billing.constants import ALLOTMENTS_ATTRIBUTE_NAME, QUOTA_ATTRIBUTE_NAME, STORAGE_RESOURCE_ATTRIBUTE_NAME
from coldfront_billing.data.quota import AllocationAssignment, NoCostQuotaEngine

from .allocation_mocks import create_ncq_allotment, storage_resource_with_cost


class TestNoCostQuotaEngine:
    """Tests for NoCostQuotaEngine.auto_assign (returns list of AllocationAssignement)."""

    @staticmethod
    def _raw_allocation(
        allocation_id: int,
        quota_tb: float | None,
        cost: str,
        *,
        allotments: tuple = (),
    ) -> Mock:
        allocation = Mock(
            spec=["id", ALLOTMENTS_ATTRIBUTE_NAME, QUOTA_ATTRIBUTE_NAME, STORAGE_RESOURCE_ATTRIBUTE_NAME],
        )
        allocation.id = allocation_id
        allocation.all_allotments = allotments
        setattr(allocation, QUOTA_ATTRIBUTE_NAME, [Mock(value=str(quota_tb))])
        setattr(
            allocation,
            STORAGE_RESOURCE_ATTRIBUTE_NAME,
            [storage_resource_with_cost(cost)],
        )
        return allocation

    def test_init_empty_allocations(self):
        engine = NoCostQuotaEngine(1, [])
        assert engine.allocations == []

    def test_allocation_assignement_str(self):
        assignment = AllocationAssignment(42, Decimal("3.5"))
        assert str(assignment) == "42 - 3.5"

    def test_auto_assign_empty_returns_empty_list(self):
        engine = NoCostQuotaEngine(1, [])
        assert engine.auto_assign(Decimal("10.0"), "TB", 1.0) == []

    def test_auto_assign_no_amount_returns_empty_list(self):
        a = self._raw_allocation(1, None, "50")
        b = self._raw_allocation(2, None, "200")
        engine = NoCostQuotaEngine(1, [a, b])
        pairs = engine.auto_assign(Decimal("15.0"), "TB", 1.0)
        assert pairs == []

    def test_auto_assign_prioritizes_higher_cost_per_tb_first(self):
        low_cost = self._raw_allocation(1, "10.0", "50")
        high_cost = self._raw_allocation(2, "10.0", "200")
        engine = NoCostQuotaEngine(1, [low_cost, high_cost])
        pairs = engine.auto_assign(Decimal("15.0"), "TB", 1)
        assert pairs == [
            AllocationAssignment(2, Decimal("10.0")),
            AllocationAssignment(1, Decimal("5.0")),
        ]

    def test_auto_assign_skips_fully_utilized_allocation(self):
        """Skip when allocation_amount equals user_amount + other_allotments_amount (TB capacity full)."""
        user_allot = create_ncq_allotment(Decimal("3.0"), "TB", user_id=1)
        other_allot = create_ncq_allotment(Decimal("7.0"), "TB", user_id=2)
        full = self._raw_allocation(1, "10.0", "100", allotments=(user_allot, other_allot))
        open_slot = self._raw_allocation(2, "10.0", "50", allotments=())
        engine = NoCostQuotaEngine(1, [full, open_slot])
        pairs = engine.auto_assign(Decimal("4.0"), "TB", 1)
        assert pairs == [AllocationAssignment(2, Decimal("4.0"))]

    def test_auto_assign_stops_when_remaining_quota_exhausted(self):
        a = self._raw_allocation(1, "10.0", "100")
        b = self._raw_allocation(2, "10.0", "200")
        engine = NoCostQuotaEngine(1, [a, b])
        pairs = engine.auto_assign(Decimal("5.0"), "TB", 1)
        assert pairs == [AllocationAssignment(2, Decimal("5.0"))]

    def test_auto_assign_single_allocation(self):
        allocation = self._raw_allocation(42, "20.0", "75")
        engine = NoCostQuotaEngine(1, [allocation])
        pairs = engine.auto_assign(Decimal("7.0"), "TB", 1)
        assert pairs == [AllocationAssignment(42, Decimal("7.0"))]

    def test_auto_assign_respects_allocation_cap(self):
        allocation = self._raw_allocation(1, "6.0", "100")
        engine = NoCostQuotaEngine(1, [allocation])
        pairs = engine.auto_assign(Decimal("100.0"), "TB", 1)
        assert pairs == [AllocationAssignment(1, Decimal("6.0"))]

    def test_auto_assign_update_existing_quota(self):
        """When allocating to an existing allocation, update the existing allocation's quota."""
        user_allot = create_ncq_allotment(Decimal("3.0"), "TB", user_id=1)
        other_allot = create_ncq_allotment(Decimal("7.0"), "TB", user_id=2)
        alloc_1 = self._raw_allocation(1, "12.0", "100", allotments=(user_allot, other_allot))
        alloc_2 = self._raw_allocation(2, "10.0", "50", allotments=())
        engine = NoCostQuotaEngine(1, [alloc_1, alloc_2])
        pairs = engine.auto_assign(Decimal("4.0"), "TB", 1)
        assert pairs == [AllocationAssignment(1, Decimal("5.0")), AllocationAssignment(2, Decimal("2.0"))]

    def test_auto_assign_with_remaining_quota_gb_prioritizes_higher_cost(self):
        """Same ordering as TB case: amounts are in GB when quota_unit is GB."""
        low_cost = self._raw_allocation(1, "10.0", "50")
        high_cost = self._raw_allocation(2, "10.0", "200")
        engine = NoCostQuotaEngine(1, [low_cost, high_cost])
        # 10 TB headroom each = 10_000 GB; 15_000 GB remaining -> 10_000 + 5_000
        pairs = engine.auto_assign(Decimal("15000.0"), "GB", 100)
        assert pairs == [
            AllocationAssignment(2, Decimal("10000.0")),
            AllocationAssignment(1, Decimal("5000.0")),
        ]

    def test_auto_assign_with_remaining_quota_gb_single_allocation(self):
        allocation = self._raw_allocation(3, "1.0", "80")
        engine = NoCostQuotaEngine(1, [allocation])
        # 1 TB = 1000 GB cap; 750 GB remaining with 1 GB increment
        pairs = engine.auto_assign(Decimal("750.0"), "GB", 1)
        assert pairs == [AllocationAssignment(3, Decimal("750.0"))]

    def test_auto_assign_with_remaining_quota_gb_respects_cap(self):
        allocation = self._raw_allocation(1, "0.5", "100")
        engine = NoCostQuotaEngine(1, [allocation])
        # 0.5 TB = 500 GB; huge remaining -> cap at 500 GB, min increment 25
        pairs = engine.auto_assign(Decimal("1000000.0"), "GB", 25)
        assert pairs == [AllocationAssignment(1, Decimal("500.0"))]

    def test_auto_assign_remaining_gb_with_other_users_allotment_in_tb(self):
        """Engine uses TB other allotments when computing GB headroom on the allocation."""
        other = create_ncq_allotment(Decimal("3.0"), "TB", user_id=99)
        alloc = self._raw_allocation(1, "10.0", "150", allotments=(other,))
        engine = NoCostQuotaEngine(1, [alloc])
        # 10 - 3 = 7 TB = 7000 GB; 9000 GB remaining -> assign 7000 GB (100 GB steps)
        pairs = engine.auto_assign(Decimal("9000.0"), "GB", 100)
        assert pairs == [AllocationAssignment(1, Decimal("7000.0"))]

    def test_auto_assign_remaining_gb_with_other_users_allotment_in_tb_quota_limit(self):
        """Engine uses TB other allotments when computing GB headroom on the allocation with limit in quota."""
        other = create_ncq_allotment(Decimal("3.0"), "TB", user_id=99)
        alloc = self._raw_allocation(1, "10.0", "150", allotments=(other,))
        engine = NoCostQuotaEngine(1, [alloc])
        # 10 - 3 = 7 TB = 7000 GB; 6000 GB remaining -> assign 6000 GB (100 GB steps)
        pairs = engine.auto_assign(Decimal("6000.0"), "GB", 100)
        assert pairs == [AllocationAssignment(1, Decimal("6000.0"))]
