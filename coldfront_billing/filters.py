from coldfront.core.project.models import Project
from django.db.models import Q, QuerySet
from django.http import QueryDict

from coldfront_billing.forms import BillingSearchForm


def filter_by_search_params(projects: QuerySet[Project], get_params: QueryDict) -> QuerySet[Project]:
    billing_search_form = BillingSearchForm(get_params)
    if billing_search_form.is_valid():
        if username := billing_search_form.cleaned_data.get('username'):
            projects = projects.filter(
                Q(pi__username__icontains=username)
                | Q(projectuser__user__username__icontains=username) & Q(projectuser__status__name='Active')
            )
        if billing_search_form.cleaned_data.get('no_cost_center'):
            projects = projects.filter(cost_center_assignment__isnull=True)
    return projects


def get_ordering(get_params: QueryDict) -> str:
    order_by = get_params.get('order_by', 'id')
    direction = get_params.get('direction', 'asc')

    field_mapping = {
        'id': 'id',
        'pi': 'pi__username',
        'title': 'title',
        'status': 'status__name',
    }
    db_field = field_mapping.get(order_by, order_by)

    if direction == 'des':
        db_field = '-' + db_field

    return db_field
