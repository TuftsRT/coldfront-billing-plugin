import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Self

from coldfront_billing.constants import QUOTA_ATTRIBUTE_NAME
from coldfront_billing.data.common import get_cost_per_tb
from coldfront_billing.utils import first_or_none


class StorageUnit(str, Enum):
    TB = 'TB'
    GB = 'GB'

    @staticmethod
    def parse(units: str) -> 'StorageUnit':
        try:
            return StorageUnit(units)
        except ValueError:
            return StorageUnit.TB


UNIT_TO_TB = {
    StorageUnit.TB: 1.0,
    StorageUnit.GB: 1.0 / 1000.0,
}


@dataclass
class BillingQuota:
    amount: float
    unit: StorageUnit

    @property
    def normalized_amount(self) -> float:
        return self.amount * UNIT_TO_TB[self.unit]

    @staticmethod
    def create(ammount: float, unit: str, *_, **__) -> 'BillingQuota':
        return BillingQuota(ammount, StorageUnit.parse(unit))


@dataclass
class NoCostQuotaAllocation:
    user_id: int
    allocation_amount: float | None
    users_allotment: BillingQuota | None
    other_allotments: list[BillingQuota]

    @property
    def user_amount(self) -> float:
        return self.users_allotment.amount if self.users_allotment else 0

    def max_possible_allocation(self, remaining_quota: float, quota_unit: str, min_increment: float) -> float:
        quota_unit = StorageUnit.parse(quota_unit)
        possible_quota = remaining_quota + self.user_amount

        if self.allocation_amount is None:
            return round(possible_quota, 2)

        tb_to_quota_unit = 1.0 / UNIT_TO_TB[StorageUnit.parse(quota_unit)]
        allocation_available_tb = max(0, self.allocation_amount - self.other_allotments_amount)
        allocation_available = allocation_available_tb * tb_to_quota_unit
        max_possible = min(possible_quota, allocation_available)
        digits = int(round(-math.log10(min_increment)))
        return round(math.floor(max_possible / min_increment) * min_increment, digits)

    @property
    def user_allotment_amount(self) -> float:
        # returns the amount of existing user allotment on this allocation in TB
        return self.users_allotment.normalized_amount if self.users_allotment else 0

    @property
    def other_allotments_amount(self) -> float:
        return sum(a.normalized_amount for a in self.other_allotments)

    @classmethod
    def create(cls, user_id: int, allocation: Any) -> Self:
        def create_no_cost_quota(allotment: Any) -> BillingQuota:
            return BillingQuota.create(
                allotment.amount,
                allotment.no_cost_quota.units,
            )

        allotments = getattr(allocation, 'all_allotments', ())

        user_allotment = next((create_no_cost_quota(a) for a in allotments if a.no_cost_quota.user_id == user_id), None)
        other_allotments = [create_no_cost_quota(a) for a in allotments if a.no_cost_quota.user_id != user_id]

        quota_attr_tb = first_or_none(getattr(allocation, QUOTA_ATTRIBUTE_NAME, None))
        # Check if allocation has quota_in_terabyte set
        try:
            allocation_amount = float(quota_attr_tb.value) if quota_attr_tb else None
        except (TypeError, ValueError):
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
    cost_per_tb: float

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
class AllocationAssignement:
    allocation_id: int
    amount: float

    def __str__(self) -> str:
        return f'{self.allocation_id} - {self.amount}'


class NoCostQuotaEngine:
    allocations: list[PricedAllocation]

    def __init__(self, user_id: int, allocations: Iterable[Any]) -> None:
        self.allocations = [PricedAllocation.create(user_id, a) for a in allocations]

    def auto_assign(
        self,
        remaining_quota: float,
        quota_unit: str,
        min_increment: float,
    ) -> list[AllocationAssignement]:
        allocation_assignements = []
        for allocation in sorted(self.allocations, key=lambda x: x.cost_per_tb, reverse=True):
            if remaining_quota == 0:
                break
            if (
                allocation.allocation_amount == allocation.user_amount + allocation.other_allotments_amount
                or allocation.allocation_amount is None
            ):
                continue
            max_possible = allocation.max_possible_allocation(remaining_quota, quota_unit, min_increment)
            if max_possible > 0:
                remaining_quota -= max_possible - allocation.user_allotment_amount
                allocation_assignements.append(AllocationAssignement(allocation.allocation_id, max_possible))

        return allocation_assignements


def parse_allocations(allocation_ids: list[str], amount_strs: list[str]) -> list[AllocationAssignement]:
    allocation_ids = [a.strip() for a in allocation_ids]
    amount_strs = [a.strip() for a in amount_strs]
    if not allocation_ids:
        raise Exception('No allocations provided')

    if not amount_strs:
        raise Exception('No amounts provided')

    if len(allocation_ids) != len(amount_strs):
        raise Exception('Invalid request: allocation and amount counts do not match.')

    assignnements = []

    for allocation_id_str, amount_str in zip(allocation_ids, amount_strs, strict=True):
        if not allocation_id_str:
            raise Exception('Invalid request: missing allocation.')

        try:
            allocation_id = int(allocation_id_str)
        except (ValueError, TypeError):
            raise Exception('The allocation id is invalid.')

        try:
            amount = float(str(amount_str).replace(',', '.'))
        except (ValueError, TypeError):
            raise Exception('The amount of allocation is invalid.')

        assignnements.append(AllocationAssignement(allocation_id, amount))

    return assignnements
