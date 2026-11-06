from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Self

from coldfront_billing.constants import ALLOTMENTS_ATTRIBUTE_NAME, QUOTA_ATTRIBUTE_NAME
from coldfront_billing.data.common import get_cost_per_tb
from coldfront_billing.enums import StorageUnit
from coldfront_billing.utils import first_or_none

UNIT_TO_TB = {
    StorageUnit.TB: Decimal("1.0"),
    StorageUnit.GB: Decimal("0.001"),
}


@dataclass
class BillingQuota:
    amount: Decimal
    unit: StorageUnit

    @property
    def amount_tb(self) -> Decimal:
        return self.amount * UNIT_TO_TB[self.unit]

    @property
    def amount_gb(self) -> Decimal:
        return self.amount_tb / UNIT_TO_TB[StorageUnit.GB]

    @staticmethod
    def create(amount: Decimal, unit: str, *_, **__) -> "BillingQuota":
        return BillingQuota(amount, StorageUnit.parse(unit))

    def create(amount: Decimal, unit: str, *_, **__) -> "BillingQuota":
        return BillingQuota(amount, StorageUnit.parse(unit))


@dataclass
class NoCostQuotaAllocation:
    user_id: int
    allocation_amount: Decimal | None
    users_allotment: BillingQuota | None
    other_allotments: list[BillingQuota]

    @property
    def user_amount(self) -> BillingQuota:
        return self.users_allotment if self.users_allotment else BillingQuota(Decimal(0), StorageUnit.TB)

    def max_possible_allocation(self, remaining_quota: Decimal, quota_unit: str, increment: int) -> Decimal:
        """
        Calculate the maximum possible allocation for this quota.

        Args:
            remaining_quota (Decimal): The remaining quota in TB.
            quota_unit (str): The unit of the quota (e.g., 'GB', 'TB').
            increment (int): The minimum increment for allocation in GB.

        Returns:
            Decimal: The maximum possible allocation in the given quota unit.
        """
        quota_unit = StorageUnit.parse(quota_unit)
        if quota_unit == StorageUnit.TB:
            possible_quota = remaining_quota + self.user_amount.amount_tb
        else:
            possible_quota = remaining_quota + self.user_amount.amount_gb
        increment_in_units = Decimal(increment) * UNIT_TO_TB[StorageUnit.parse("GB")] / UNIT_TO_TB[quota_unit]
        if self.allocation_amount is None:
            # increment is always in GB, so we need to convert it to the quota unit for comparison
            return possible_quota.quantize(increment_in_units)

        tb_to_quota_unit = Decimal("1.0") / UNIT_TO_TB[quota_unit]
        allocation_available_tb = max(0, self.allocation_amount - self.other_allotments_amount)
        allocation_available = allocation_available_tb * tb_to_quota_unit
        max_possible = min(possible_quota, allocation_available)
        # increment_in_units is already calculated
        return (max_possible // increment_in_units) * increment_in_units

    @property
    def user_allotment_amount(self) -> Decimal:
        # returns the amount of existing user allotment on this allocation in TB
        return self.users_allotment.amount_tb if self.users_allotment else Decimal("0")

    @property
    def other_allotments_amount(self) -> Decimal:
        return sum((a.amount_tb for a in self.other_allotments), Decimal("0"))

    @classmethod
    def create(cls, user_id: int, allocation: Any) -> Self:
        def create_no_cost_quota(allotment: Any) -> BillingQuota:
            return BillingQuota.create(
                allotment.amount_tb,
                allotment.no_cost_quota.units,
            )

        allotments = getattr(allocation, ALLOTMENTS_ATTRIBUTE_NAME, ())

        user_allotment = next((create_no_cost_quota(a) for a in allotments if a.no_cost_quota.user_id == user_id), None)
        other_allotments = [create_no_cost_quota(a) for a in allotments if a.no_cost_quota.user_id != user_id]

        quota_attr_tb = first_or_none(getattr(allocation, QUOTA_ATTRIBUTE_NAME, None))
        # Check if allocation has quota_in_terabyte set
        try:
            allocation_amount = Decimal(quota_attr_tb.value) if quota_attr_tb else None
        except (TypeError, ValueError, InvalidOperation):
            allocation_amount = None

        return cls(
            user_id=user_id,
            allocation_amount=allocation_amount,
            users_allotment=user_allotment,
            other_allotments=other_allotments,
        )


@dataclass
class PricedAllocation(NoCostQuotaAllocation):
    allocation_id: int
    cost_per_tb: Decimal

    @classmethod
    def create(cls, user_id: int, allocation: Any) -> Self:
        base = NoCostQuotaAllocation.create(user_id, allocation)
        cost_per_tb = get_cost_per_tb(allocation, 0)
        return cls(
            **base.__dict__,
            allocation_id=allocation.id,
            cost_per_tb=cost_per_tb,
        )


@dataclass
class AllocationAssignment:
    allocation_id: int
    amount: Decimal

    def __str__(self) -> str:
        return f"{self.allocation_id} - {self.amount}"


class NoCostQuotaEngine:
    allocations: list[PricedAllocation]

    def __init__(self, user_id: int, allocations: Iterable[Any]) -> None:
        self.allocations = [PricedAllocation.create(user_id, a) for a in allocations]

    def auto_assign(
        self,
        remaining_quota: Decimal,
        quota_unit: str,
        min_increment: int,
    ) -> list[AllocationAssignment]:
        allocation_assignments = []
        for allocation in sorted(self.allocations, key=lambda x: x.cost_per_tb, reverse=True):
            if remaining_quota == 0:
                break
            if (
                allocation.allocation_amount == allocation.user_amount.amount_tb + allocation.other_allotments_amount
                or allocation.allocation_amount is None
            ):
                continue
            max_possible = allocation.max_possible_allocation(remaining_quota, quota_unit, min_increment)
            if max_possible > 0:
                remaining_quota -= max_possible - allocation.user_amount.amount_tb
                allocation_assignments.append(AllocationAssignment(allocation.allocation_id, max_possible))

        return allocation_assignments


def parse_allocations(allocation_ids: list[str], amount_strs: list[str]) -> list[AllocationAssignment]:
    allocation_ids = [a.strip() for a in allocation_ids]
    amount_strs = [a.strip() for a in amount_strs]
    if not allocation_ids:
        raise Exception("No allocations provided")

    if not amount_strs:
        raise Exception("No amounts provided")

    if len(allocation_ids) != len(amount_strs):
        raise Exception("Invalid request: allocation and amount counts do not match.")

    assignments = []

    for allocation_id_str, amount_str in zip(allocation_ids, amount_strs, strict=True):
        if not allocation_id_str:
            raise Exception("Invalid request: missing allocation.")

        try:
            allocation_id = int(allocation_id_str)
        except (ValueError, TypeError):
            raise Exception("The allocation id is invalid.")

        try:
            amount = Decimal(amount_str.replace(",", ".")).quantize(Decimal("0.01"))
        except (ValueError, TypeError, InvalidOperation):
            raise Exception("The amount of allocation is invalid.")

        assignments.append(AllocationAssignment(allocation_id, amount))

    return assignments
