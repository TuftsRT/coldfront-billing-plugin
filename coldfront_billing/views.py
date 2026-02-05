import logging

from coldfront.core.allocation.models import Allocation, AllocationAttribute
from coldfront.core.project.forms import ProjectSearchForm
from coldfront.core.project.models import Project
from coldfront.core.resource.models import Resource, ResourceAttribute, ResourceType
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.db.models import Prefetch
from django.http import HttpResponse
from django.views.generic import ListView
from django.db.models import Q

from coldfront_billing.constants import (
    BILLING_ATTRIBUTE_NAME,
    COST_ATTR_NAME,
    COST_ATTRIBUTE_NAME,
    QUOTA_ATTR_NAME,
    QUOTA_ATTRIBUTE_NAME,
    STORAGE_RESOURCE_ATTRIBUTE_NAME,
)
from coldfront_billing.data import BillingAllocation
from coldfront_billing.forms import BillingSearchForm

logger = logging.getLogger('BillingView')


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
    paginate_by = 25

    def get_queryset(self):
        order_by = self.request.GET.get('order_by', 'id')
        direction = self.request.GET.get('direction', 'asc')

        if direction == 'des':
            order_by = '-' + order_by

        projects = Project.objects.all()

        billing_search_form = BillingSearchForm(self.request.GET)
        if billing_search_form.is_valid():

            if username := billing_search_form.cleaned_data.get('username'):
                projects = projects.filter(
                    Q(pi__username__icontains=username)
                    | Q(projectuser__user__username__icontains=username)
                    & Q(projectuser__status__name="Active")
                )

        if not self.request.user.is_superuser:
            projects = projects.filter(
                projectuser__user=self.request.user,
                projectuser__role__name='Billing',
                projectuser__status__name='Active',
            ).distinct()

        if not (storage_type := ResourceType.objects.only('id').filter(name='Storage').first()):
            return projects.select_related('pi', 'status').order_by(order_by)

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
        projects = projects.select_related('pi', 'status').prefetch_related(allocations_prefetch)

        return projects.order_by(order_by)

    def get_context_data(self, **kwargs):
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
            # Cost centers currently set to '-'
            project.cost_centers = '-'

        context['billing_search_form'] = BillingSearchForm(self.request.GET)
        context['expand_accordion'] = 'show' if self.request.GET else ''
        filter_params = self.request.GET.copy()
        if 'page' in filter_params:
            del filter_params['page']
        if 'order_by' in filter_params:
            del filter_params['order_by']
        if 'direction' in filter_params:
            del filter_params['direction']

        context['filter_parameters'] = filter_params.urlencode()

        return context


def b_link(request):
    return HttpResponse('<h1>This is the B-Link Page</h1>')
