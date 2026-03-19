"""View mixins for billing allocation prefetching."""

from abc import ABC, abstractmethod
from typing import Callable

from coldfront.core.allocation.models import Allocation, AllocationAttribute
from coldfront.core.resource.models import Resource, ResourceAttribute
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.http import HttpRequest

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


class PrefetchPaginationMixin:
    """Mixin providing Prefetch configurations for billing queries."""

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


class BillingAllocationPrefetchMixin(PrefetchPaginationMixin):
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


class ListViewStateMixin(ABC):
    """Mixin providing sorting, filtering, and pagination related data."""

    request: HttpRequest
    paginate_by = PAGINATE_BY
    db_order_map = {}

    @property
    def request_get(self):
        return self.request.GET

    def get_pagination_params(self) -> dict:
        all_params = self.request_get.copy()
        all_params.pop('page', None)

        filter_params = all_params.copy()
        for key in ('order_by', 'direction'):
            filter_params.pop(key, None)

        return {
            'filter_parameters': filter_params.urlencode(),
            'all_params': all_params.urlencode(),
            'return_params': self.request_get.urlencode(),
            'expand_accordion': 'show' if filter_params else '',
        }

    def get_extended_pagination_params(self, allocations: list) -> dict:
        paginator = Paginator(allocations, self.paginate_by)
        page_number = self.request_get.get('page', 1)
        page_obj = paginator.get_page(page_number)

        return self.get_pagination_params() | {
            'allocations': page_obj.object_list,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
        }

    def get_ordering(self) -> str:
        order_by = self.request_get.get('order_by', 'id')

        db_field = self.db_order_map.get(order_by, order_by)

        prefix = '-' if self.request_get.get('direction') == 'des' else ''

        return f'{prefix}{db_field}'

    @abstractmethod
    def get_object_ordering(self) -> tuple[Callable, bool]:
        pass


class BillingListViewStateMixin(ListViewStateMixin):
    """Mixin providing sorting, filtering, and pagination related data for billing list view."""

    db_order_map = {
        'id': 'id',
        'pi': 'pi__username',
        'title': 'title',
        'status': 'status__name',
    }

    def get_object_ordering(self) -> tuple[Callable, bool]:
        """Used for sorting BillingAllocation objects - not DB"""
        order_by = self.request_get.get('order_by', 'id')
        direction = self.request_get.get('direction', 'asc')

        def key_funcion(allocation: BillingAllocation):
            extra = allocation.extra

            def low(key: str) -> str:
                return (extra.get(key) or '').lower()

            match order_by:
                case 'id':
                    return allocation.allocation_id
                case 'project':
                    return low('project_title')
                case 'pi':
                    return low('pi_name')
                case 'resource_name':
                    return low('resource_name')
                case 'status':
                    return low('status')
                case 'end_date':
                    v = extra.get('end_date')
                    return '' if v in (None, '-') else v
                case 'cost':
                    return allocation.total_cost
                case _:
                    return allocation.allocation_id

        return key_funcion, direction == 'des'


class NoCostQuotaStateMixin(ListViewStateMixin):
    """Mixin providing sorting, filtering, and pagination related data for no-cost quota list view."""

    db_order_map = {
        'owner': 'user__username',
        'quota_type': 'quota_type',
        'description': 'description',
        'amount': 'amount_normalized',
        'remaining': 'remaining_normalized',
    }

    def get_object_ordering(self) -> tuple[Callable, bool]:
        """Used for sorting assign view allocation row dicts."""
        order_by = self.request_get.get('order_by', 'id')
        direction = self.request_get.get('direction', 'asc')

        def key_func(row: dict):
            allocation = row['allocation']
            match order_by:
                case 'id':
                    return allocation.id
                case 'project':
                    return (allocation.project.title or '').lower()
                case 'pi':
                    return (allocation.project.pi.username or '').lower()
                case 'resource_name':
                    return (row.get('resource_name') or '').lower()
                case 'amount':
                    v = row.get('quota_amount', 0.0)
                    return float(v)
                case _:
                    return allocation.id

        return key_func, direction == 'des'


class NoCostQuotaAssignViewMixin(NoCostQuotaStateMixin):
    def get_pagination_params(self) -> dict:
        pagination_params = super().get_pagination_params()
        # Exclude selected_quota from return_params

        request_get = self.request_get.copy()
        request_get.pop('selected_quota', None)
        pagination_params['return_params'] = request_get.urlencode()

        return pagination_params
