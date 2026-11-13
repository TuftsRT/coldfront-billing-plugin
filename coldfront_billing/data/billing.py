from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List

from coldfront.core.allocation.models import Allocation

from coldfront_billing.constants import (
    ALLOTMENTS_ATTRIBUTE_NAME,
    DEFAULT_BILLING_COST,
    DEFAULT_BILLING_QUOTA,
    QUOTA_ATTRIBUTE_NAME,
    STORAGE_RESOURCE_ATTRIBUTE_NAME,
)

from .common import get_cost_per_tb
from .quota import BillingQuota


def monthly_cost(quota_tb: Decimal, cost_per_tb: Decimal) -> Decimal:
    """The monthly cost of `quota_tb` at `cost_per_tb`: the quota rounded up to 0.1 TB and the price up to the cent.
    Raises InvalidOperation for a quota too large to round (1e30, say)."""
    calculation = quota_tb.quantize(Decimal("0.1"), rounding="ROUND_CEILING") * cost_per_tb.quantize(
        Decimal("0.01"), rounding="ROUND_CEILING"
    )
    return calculation.quantize(Decimal("0.01"))  # Round to 2 decimal places


def predicted_monthly_cost(
    quota_tb: Decimal, cost_per_tb: Decimal, user_remaining_quota_tb: Decimal, no_cost_tb: Decimal = Decimal(0)
) -> tuple[Decimal, Decimal]:
    """The monthly cost of `quota_tb`, less `no_cost_tb` already allotted and as much of the user's remaining
    no-cost quota as covers the rest, and the amount of that remaining quota applied."""
    unpaid_quota = max(quota_tb - no_cost_tb, Decimal(0))
    applied_quota = Decimal(0) if user_remaining_quota_tb <= 0 else min(user_remaining_quota_tb, unpaid_quota)
    billable_quota = max(unpaid_quota - applied_quota, Decimal(0))
    return monthly_cost(billable_quota, cost_per_tb), applied_quota


@dataclass
class BillingAllocation:
    allocation_id: int
    project_id: int
    quota_tb: Decimal
    cost_per_tb: Decimal
    extra: Dict[str, Any] = field(default_factory=dict)
    no_cost_quotas: List[BillingQuota] = field(default_factory=list)

    @property
    def total_cost(self) -> Decimal:
        total_cost, _ = self.get_predicted_cost(Decimal(0))
        return total_cost

    def get_predicted_cost(self, user_remaining_quota_tb: Decimal) -> tuple[Decimal, Decimal]:
        total_no_cost_quota = sum((ncq.amount_tb for ncq in self.no_cost_quotas), Decimal(0))
        return predicted_monthly_cost(self.quota_tb, self.cost_per_tb, user_remaining_quota_tb, total_no_cost_quota)

    def calculate_cost(self, quota_tb: Decimal) -> Decimal:
        return monthly_cost(quota_tb, self.cost_per_tb)

    @classmethod
    def parse(
        cls,
        allocation,
        default_quota: Decimal,
        default_cost: Decimal,
        new_quota: Decimal | None = None,
    ) -> "BillingAllocation":
        if quota_attrs := getattr(allocation, QUOTA_ATTRIBUTE_NAME, None):
            quota_raw = quota_attrs[0].value
            try:
                dec_quota = Decimal(quota_raw) if quota_raw is not None else default_quota
                quota_tb = dec_quota if dec_quota >= 0 else default_quota
            except (InvalidOperation, ValueError):
                quota_tb = default_quota
        else:
            quota_tb = default_quota

        if new_quota is not None:
            quota_tb += new_quota

        cost_per_tb = get_cost_per_tb(allocation, default_cost)
        if (project := getattr(allocation, "project", None)) is not None:
            project_title = getattr(project, "title", "-")
            pi = getattr(project, "pi", None)
            project_extra = {
                "project_title": project_title or "-",
                "pi_name": pi.username if pi else "-",
            }
        else:
            project_extra = {
                "project_title": "-",
                "pi_name": "-",
            }

        storage_resources = getattr(allocation, STORAGE_RESOURCE_ATTRIBUTE_NAME, [])
        resource_name = storage_resources[0].name if storage_resources else "-"

        allotments = getattr(allocation, ALLOTMENTS_ATTRIBUTE_NAME, [])
        no_cost_quotas = [
            BillingQuota.create(allotment.amount_tb, allotment.no_cost_quota.units) for allotment in allotments
        ]

        return cls(
            allocation_id=allocation.id,
            project_id=allocation.project_id,
            quota_tb=quota_tb,
            cost_per_tb=cost_per_tb,
            extra=project_extra
            | {
                "resource_name": resource_name,
                "status": allocation.status.name,
                "end_date": getattr(allocation, "end_date", None) or "-",
            },
            no_cost_quotas=no_cost_quotas,
        )


def create_billing_allocations(allocation_objs: list[Allocation]) -> list[BillingAllocation]:
    return [BillingAllocation.parse(a, DEFAULT_BILLING_QUOTA, DEFAULT_BILLING_COST) for a in allocation_objs]
