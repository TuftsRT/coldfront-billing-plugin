from typing import Any, Callable

from django.http import QueryDict

from coldfront_billing.data import BillingAllocation


def get_ordering(params: QueryDict) -> str:
    order_by = params.get('order_by', 'id')

    db_field = {
        'id': 'id',
        'pi': 'pi__username',
        'title': 'title',
        'status': 'status__name',
    }.get(order_by, order_by)

    prefix = '-' if params.get('direction') == 'des' else ''

    return f'{prefix}{db_field}'


def get_no_cost_quota_ordering(params: QueryDict) -> str:
    order_by = params.get('order_by', 'owner')

    db_field = {
        'owner': 'user__username',
        'quota_type': 'quota_type',
        'description': 'description',
        'amount': 'amount',
        'remaining': 'remaining',
    }.get(order_by, 'user__username')

    prefix = '-' if params.get('direction') == 'des' else ''

    return f'{prefix}{db_field}'


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
