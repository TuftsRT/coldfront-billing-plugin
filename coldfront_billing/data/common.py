from decimal import Decimal, InvalidOperation

from coldfront_billing.constants import COST_ATTRIBUTE_NAME, STORAGE_RESOURCE_ATTRIBUTE_NAME
from coldfront_billing.utils import first_or_none


def parse_cost_per_tb(value, default_cost: Decimal) -> Decimal:
    """A cost-per-TB attribute's value as a Decimal: `default_cost` when it's missing, not a number, or
    negative. The one rule for it, for allocations (get_cost_per_tb) and the request form's estimate."""
    if value is None:
        return default_cost
    try:
        cost = Decimal(value)
        return cost if cost >= 0 else default_cost  # NaN's comparison raises InvalidOperation
    except (InvalidOperation, ValueError, TypeError):
        return default_cost


def get_cost_per_tb(
    allocation,
    default_cost: Decimal,
) -> Decimal:
    storage_resource = first_or_none(getattr(allocation, STORAGE_RESOURCE_ATTRIBUTE_NAME, []))

    if storage_resource and (cost_attrs := getattr(storage_resource, COST_ATTRIBUTE_NAME, None)):
        return parse_cost_per_tb(cost_attrs[0].value, default_cost)
    return default_cost
