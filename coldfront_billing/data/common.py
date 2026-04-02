from coldfront_billing.constants import COST_ATTRIBUTE_NAME, STORAGE_RESOURCE_ATTRIBUTE_NAME
from coldfront_billing.utils import first_or_none, parse_float


def get_cost_per_tb(
    allocation,
    default_cost: float,
) -> float:
    storage_resource = first_or_none(getattr(allocation, STORAGE_RESOURCE_ATTRIBUTE_NAME, []))

    if storage_resource and (cost_attrs := getattr(storage_resource, COST_ATTRIBUTE_NAME, None)):
        float_cost = parse_float(cost_attrs[0].value, default_cost)
        return float_cost if float_cost >= 0 else default_cost
    return default_cost
