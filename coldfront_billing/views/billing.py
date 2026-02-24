import json
from typing import Any, Dict

from coldfront.core.allocation.models import Allocation, AllocationAttribute
from coldfront.core.project.models import Project
from coldfront.core.resource.models import Resource, ResourceAttribute, ResourceType
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch, Q, QuerySet
from django.views.generic import ListView

from coldfront_billing.constants import (
    BILLING_ATTRIBUTE_NAME,
    COST_ATTR_NAME,
    COST_ATTRIBUTE_NAME,
    QUOTA_ATTR_NAME,
    QUOTA_ATTRIBUTE_NAME,
    STORAGE_RESOURCE_ATTRIBUTE_NAME,
)
from coldfront_billing.data import BillingAllocation
from coldfront_billing.filters import filter_by_search_params, get_ordering
from coldfront_billing.forms import BillingSearchForm
from coldfront_billing.models import CostCenter

from .mixins import PAGINATE_BY

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


class BillingView(LoginRequiredMixin, ListView):
    model = Project
    template_name = 'billing/billing.html'
    context_object_name = 'project_list'
    paginate_by = PAGINATE_BY

    def get_queryset(self) -> QuerySet[Project]:
        projects = Project.objects.all()
        ordering = get_ordering(get_params=self.request.GET)
        projects = filter_by_search_params(projects=projects, get_params=self.request.GET)

        if not self.request.user.is_superuser:
            projects = projects.filter(
                Q(
                    projectuser__user=self.request.user,
                    projectuser__role__name='Billing',
                    projectuser__status__name='Active',
                )
                | Q(pi=self.request.user)
            ).distinct()

        if not (storage_type := ResourceType.objects.only('id').filter(name='Storage').first()):
            return projects.select_related('pi', 'status').order_by(ordering)

        # Restrict to only projects that actually have paid Storage allocations
        projects = projects.filter(
            allocation__resources__resource_type_id=storage_type.id,
            allocation__resources__requires_payment=True,
        ).distinct()

        # Prefetch only what we need for cost calculation
        cost_attr_prefetch = Prefetch(
            'resourceattribute_set',
            queryset=ResourceAttribute.objects.filter(resource_attribute_type__name=COST_ATTR_NAME).only(
                'resource_id', 'value', 'resource_attribute_type_id'
            ),
            to_attr=COST_ATTRIBUTE_NAME,
        )

        # Prefetch only paid Storage resources + their cost attr
        paid_storage_resources_prefetch = Prefetch(
            'resources',
            queryset=Resource.objects.filter(
                resource_type_id=storage_type.id,
                requires_payment=True,
            ).prefetch_related(cost_attr_prefetch),
            to_attr=STORAGE_RESOURCE_ATTRIBUTE_NAME,
        )

        # Prefetch only the allocation attribute holding quota_attr_name
        quota_attr_prefetch = Prefetch(
            'allocationattribute_set',
            queryset=AllocationAttribute.objects.filter(allocation_attribute_type__name=QUOTA_ATTR_NAME).only(
                'allocation_id', 'value'
            ),
            to_attr=QUOTA_ATTRIBUTE_NAME,
        )

        allocations_prefetch = Prefetch(
            'allocation_set',
            queryset=Allocation.objects.filter(
                resources__resource_type_id=storage_type.id,
                resources__requires_payment=True,
                status__name='Active',
            )
            .distinct()
            .prefetch_related(quota_attr_prefetch, paid_storage_resources_prefetch),
            to_attr=BILLING_ATTRIBUTE_NAME,
        )
        # Fetch only projects that have such allocations
        projects = projects.select_related('pi', 'status').prefetch_related(
            allocations_prefetch, 'cost_center_assignment'
        )

        return projects.order_by(ordering)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        # Count projects from the list to avoid duplicate query
        context['projects_count'] = len(context['project_list'])

        project_list = context.get('project_list', [])
        for project in project_list:
            billing_allocations = [
                BillingAllocation.parse(a, default_quota, default_cost)
                for a in getattr(project, BILLING_ATTRIBUTE_NAME, [])
            ]
            project_cost = sum(b.total_cost for b in billing_allocations)
            project.cost = f'${project_cost}'

            # 2. Handle Cost Center & JSON Serialization safely
            try:
                assignment_obj = project.cost_center_assignment
                project.cost_centers = assignment_obj.get_cost_centers_display()
                project.assignments_json = json.dumps(assignment_obj.assignments)
            except ObjectDoesNotExist:
                project.cost_centers = '-'
                project.assignments_json = '{}'

        request_get = self.request.GET
        pagination_params = request_get.copy()
        pagination_params.pop('page', None)

        filter_params = pagination_params.copy()
        for key in ('order_by', 'direction'):
            filter_params.pop(key, None)

        return context | {
            'billing_search_form': BillingSearchForm(request_get),
            'departments': CostCenter.objects.all(),
            'filter_parameters': filter_params.urlencode(),
            'filter_parameters_with_order_by': pagination_params.urlencode(),
            'expand_accordion': 'show' if filter_params else '',
        }
