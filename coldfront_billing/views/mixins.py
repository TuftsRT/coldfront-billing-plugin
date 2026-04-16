"""View mixins for billing allocation prefetching."""

from abc import ABC, abstractmethod
from typing import Callable

from django.conf import settings
from django.core.paginator import Paginator
from django.http import HttpRequest

from coldfront_billing.data import BillingAllocation

PAGINATE_BY = getattr(settings, 'COLDFRONT_BILLING_PAGINATE_BY', 25)


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
        is_paginated = page_obj.has_other_pages()

        return self.get_pagination_params() | {
            'allocations': page_obj.object_list,
            'page_obj': page_obj,
            'is_paginated': is_paginated,
            'allocations_count': paginator.count if is_paginated else len(allocations),
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
                case 'resource_name':
                    return (row.get('resource_name') or '').lower()
                case 'amount':
                    v = row.get('quota_amount', 0.0)
                    return float(v) if v != '-' else 0.0
                case _:
                    return allocation.id

        return key_func, direction == 'des'


class NoCostQuotaAssignViewMixin(NoCostQuotaStateMixin):
    def get_pagination_params(self) -> dict:
        pagination_params = super().get_pagination_params()

        # selected_quota and back must stay in filter_parameters so sort/pagination
        # links keep the assign view and manage return state. Kinda W/A rather than good solution
        has_allocation_search = bool(self.request_get.get('project') or self.request_get.get('status'))
        # Accordion should reflect only allocation search fields (not navigation params)
        pagination_params['expand_accordion'] = 'show' if has_allocation_search else ''

        return pagination_params
