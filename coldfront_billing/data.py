import math
from dataclasses import dataclass

from coldfront_billing.constants import COST_ATTRIBUTE_NAME, QUOTA_ATTRIBUTE_NAME, STORAGE_RESOURCE_ATTRIBUTE_NAME


def _first_or_none(sequence):
    return sequence[0] if sequence else None


def _parse_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass
class BillingAllocation:
    allocation_id: int
    project_id: int
    quota_tb: int
    cost_per_tb: int

    @property
    def total_cost(self):
        return int(math.ceil(self.quota_tb)) * int(self.cost_per_tb)

    @classmethod
    def parse(cls, allocation, default_quota: int, default_cost: int):
        if quota_attrs := getattr(allocation, QUOTA_ATTRIBUTE_NAME, None):
            quota_raw = quota_attrs[0].value
            quota_tb = _parse_float(quota_raw, default_quota)
        else:
            quota_tb = default_quota

        storage_resource = _first_or_none(getattr(allocation, STORAGE_RESOURCE_ATTRIBUTE_NAME, []))

        if storage_resource and (cost_attrs := getattr(storage_resource, COST_ATTRIBUTE_NAME, None)):
            cost_per_tb = _parse_float(cost_attrs[0].value, default_cost)
        else:
            cost_per_tb = default_cost

        return cls(
            allocation_id=allocation.id,
            project_id=allocation.project_id,
            quota_tb=quota_tb,
            cost_per_tb=cost_per_tb,
        )
