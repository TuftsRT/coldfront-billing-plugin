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
