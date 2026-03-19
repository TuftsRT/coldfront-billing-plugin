from typing import Any, Callable

from django.http import QueryDict

from coldfront_billing.data import BillingAllocation


def get_allocation_ordering(get_params: QueryDict) -> tuple[Callable[..., Any], bool]:
    """Used for sorting BillingAllocation objects - not DB"""
    order_by = get_params.get('order_by', 'id')
    direction = get_params.get('direction', 'asc')

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
