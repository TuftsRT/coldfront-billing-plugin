import json
from typing import Any, Dict

from coldfront.core.allocation.models import Allocation
from coldfront.core.project.models import Project
from coldfront.core.resource.models import ResourceType
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch, Q, QuerySet
from django.views.generic import ListView

from coldfront_billing.constants import BILLING_ATTRIBUTE_NAME
from coldfront_billing.filters import filter_by_search_params, get_ordering
from coldfront_billing.forms import BillingSearchForm
from coldfront_billing.models import CostCenter

from .mixins import BillingAllocationPrefetchMixin


class BillingView(LoginRequiredMixin, BillingAllocationPrefetchMixin, ListView):
    model = Project
    template_name = 'billing/billing.html'
    context_object_name = 'project_list'
    paginate_by = 25

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

        allocations_prefetch = Prefetch(
            'allocation_set',
            queryset=Allocation.objects.filter(
                resources__resource_type_id=storage_type.id,
                resources__requires_payment=True,
                status__name='Active',
            )
            .distinct()
            .prefetch_related(
                self.get_quota_attr_prefetch(),
                self.get_paid_storage_resources_prefetch(storage_type.id),
            ),
            to_attr=BILLING_ATTRIBUTE_NAME,
        )
        projects = projects.select_related('pi', 'status').prefetch_related(
            allocations_prefetch, 'cost_center_assignment'
        )

        return projects.order_by(ordering)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        # Count projects from the list to avoid duplicate query
        context['projects_count'] = len(context['project_list'])

        for project in context.get('project_list', []):
            billing_allocations = self.create_billing_allocations(
                [a for a in getattr(project, BILLING_ATTRIBUTE_NAME, [])]
            )
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

        context['billing_search_form'] = BillingSearchForm(self.request.GET)
        context['expand_accordion'] = 'show' if self.request.GET else ''
        context['departments'] = CostCenter.objects.all()

        filter_params = self.request.GET.copy()
        for key in ('page', 'order_by', 'direction'):
            filter_params.pop(key, None)
        context['filter_parameters'] = filter_params.urlencode()

        return context
