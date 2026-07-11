from decimal import Decimal, InvalidOperation

from coldfront_billing.constants import COST_ATTRIBUTE_NAME, STORAGE_RESOURCE_ATTRIBUTE_NAME
from coldfront_billing.utils import first_or_none


def get_cost_per_tb(
    allocation,
    default_cost: Decimal,
) -> Decimal:
    storage_resource = first_or_none(getattr(allocation, STORAGE_RESOURCE_ATTRIBUTE_NAME, []))

    if storage_resource and (cost_attrs := getattr(storage_resource, COST_ATTRIBUTE_NAME, None)):
        try:
            dec_cost = Decimal(cost_attrs[0].value) if cost_attrs[0].value is not None else default_cost
            return dec_cost if dec_cost >= 0 else default_cost
        except (InvalidOperation, ValueError):
            return default_cost
    return default_cost
