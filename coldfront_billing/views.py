import logging
import math

from coldfront.core.allocation.models import Allocation, AllocationAttribute
from coldfront.core.project.models import Project
from coldfront.core.resource.models import ResourceType
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch
from django.http import HttpResponse
from django.views.generic import ListView

from coldfront_billing.constants import quota_attr_name

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


def _first_or_none(sequence):
    return sequence[0] if sequence else None


def _parse_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class BillingView(LoginRequiredMixin, ListView):
    model = Project
    template_name = 'billing/billing.html'
    context_object_name = 'project_list'

    def get_queryset(self):
        order_by = self.request.GET.get('order_by', 'id')
        direction = self.request.GET.get('direction', 'asc')

        if direction == 'desc':
            order_by = '-' + order_by

        projects = Project.objects.all()

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

        # Prefetch only the allocation attribute holding quota_attr_name
        quota_attr_prefetch = Prefetch(
            'allocationattribute_set',
            queryset=AllocationAttribute.objects.filter(allocation_attribute_type__name=quota_attr_name).only(
                'allocation_id', 'value'
            ),
            to_attr='quota_attrs',
        )

        allocations_prefetch = Prefetch(
            'allocation_set',
            queryset=Allocation.objects.filter(
                resources__resource_type_id=storage_type.id,
                resources__requires_payment=True,
            )
            .distinct()
            .prefetch_related(quota_attr_prefetch),
            to_attr='billing_allocations',
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
            project_cost = 0
            for alloc in getattr(project, 'billing_allocations', []):
                quota_value = alloc.quota_attrs[0].value if alloc.quota_attrs else None
                logger.info(f'Project: {project.id} Quota attr: {quota_value}')
                quota_tb = math.ceil(_parse_float(quota_value, default_quota))

                project_cost += quota_tb * default_cost

            project.cost = f'${project_cost}'
            # Cost centers currently set to '-'
            project.cost_centers = '-'

        return context


def b_link(request):
    return HttpResponse('<h1>This is the B-Link Page</h1>')
