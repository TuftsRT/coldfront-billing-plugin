from coldfront.core.allocation.models import Allocation
from django.conf import settings

from coldfront_billing.data import BillingAllocation

default_quota = getattr(
    settings,
    'COLDFRONT_BILLING_DEFAULT_QUOTA',
    0,
)
default_cost = getattr(
    settings,
    'COLDFRONT_BILLING_DEFAULT_COST',
    10,
)


def create_billing_allocations(allocation_objs: list[Allocation]) -> list[BillingAllocation]:
    return [BillingAllocation.parse(a, default_quota, default_cost) for a in allocation_objs]
