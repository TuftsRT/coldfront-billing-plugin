import math
from dataclasses import dataclass
from enum import Enum


class StorageUnit(str, Enum):
    TB = 'TB'
    GB = 'GB'

    @staticmethod
    def parse(units: str):
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
    def user_amount(self):
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

    @staticmethod
    def create(user_id: int, allocation_amount: float, allotments) -> 'NoCostQuotaAllocation':
        def create_no_cost_quota(allotment):
            return BillingQuota.create(
                allotment.amount,
                allotment.no_cost_quota.units,
            )

        user_allotment = next((create_no_cost_quota(a) for a in allotments if a.no_cost_quota.user_id == user_id), None)
        other_allotments = [create_no_cost_quota(a) for a in allotments if a.no_cost_quota.user_id != user_id]

        return NoCostQuotaAllocation(
            user_id=user_id,
            allocation_amount=allocation_amount,
            users_allotment=user_allotment,
            other_allotments=other_allotments,
        )
