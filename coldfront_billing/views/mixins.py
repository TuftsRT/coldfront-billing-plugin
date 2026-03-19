"""View mixins for billing allocation prefetching."""

from coldfront.core.allocation.models import Allocation, AllocationAttribute
from coldfront.core.resource.models import Resource, ResourceAttribute
from django.conf import settings
from django.db.models import Prefetch
from django.http import QueryDict

from coldfront_billing.constants import (
    COST_ATTR_NAME,
    COST_ATTRIBUTE_NAME,
    NO_COST_QUOTA_DATA_ATTRIBUTE_NAME,
    QUOTA_ATTR_NAME,
    QUOTA_ATTRIBUTE_NAME,
    STORAGE_RESOURCE_ATTRIBUTE_NAME,
)
from coldfront_billing.data import BillingAllocation
from coldfront_billing.models import NoCostQuotaAllotment

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
PAGINATE_BY = getattr(settings, 'COLDFRONT_BILLING_PAGINATE_BY', 25)


def get_pagination_params(request_get: QueryDict) -> dict:
    all_params = request_get.copy()
    all_params.pop('page', None)

    filter_params = all_params.copy()
    for key in ('order_by', 'direction'):
        filter_params.pop(key, None)

    return {
        'filter_parameters': filter_params.urlencode(),
        'all_params': all_params.urlencode(),
        'return_params': request_get.urlencode(),
        'expand_accordion': 'show' if filter_params else '',
    }


class BillingAllocationPrefetchMixin:
    """Mixin providing Prefetch configurations for billing allocation queries."""

    @staticmethod
    def get_cost_attr_prefetch() -> Prefetch:
        """Return Prefetch for resource cost attribute."""
        return Prefetch(
            'resourceattribute_set',
            queryset=ResourceAttribute.objects.filter(resource_attribute_type__name=COST_ATTR_NAME).only(
                'resource_id', 'value', 'resource_attribute_type_id'
            ),
            to_attr=COST_ATTRIBUTE_NAME,
        )

    def get_paid_storage_resources_prefetch(self, storage_type_id: int) -> Prefetch:
        """Return Prefetch for paid Storage resources with cost attribute."""
        return Prefetch(
            'resources',
            queryset=Resource.objects.filter(
                resource_type_id=storage_type_id,
                requires_payment=True,
            ).prefetch_related(self.get_cost_attr_prefetch()),
            to_attr=STORAGE_RESOURCE_ATTRIBUTE_NAME,
        )

    @staticmethod
    def get_quota_attr_prefetch() -> Prefetch:
        """Return Prefetch for allocation quota attribute."""
        return Prefetch(
            'allocationattribute_set',
            queryset=AllocationAttribute.objects.filter(allocation_attribute_type__name=QUOTA_ATTR_NAME).only(
                'allocation_id', 'value'
            ),
            to_attr=QUOTA_ATTRIBUTE_NAME,
        )

    @staticmethod
    def get_no_cost_quota_allotments_prefetch() -> Prefetch:
        return Prefetch(
            'no_cost_quota_allotments',
            queryset=NoCostQuotaAllotment.objects.select_related('no_cost_quota').only(
                'id',
                'allocation_id',
                'amount',
                'no_cost_quota__units',
            ),
            to_attr=NO_COST_QUOTA_DATA_ATTRIBUTE_NAME,
        )

    @staticmethod
    def create_billing_allocations(allocation_objs: list[Allocation]) -> list[BillingAllocation]:
        return [BillingAllocation.parse(a, default_quota, default_cost) for a in allocation_objs]
