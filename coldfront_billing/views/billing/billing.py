import json
from typing import Any, Dict

from coldfront.core.allocation.models import Allocation
from coldfront.core.project.models import Project
from coldfront.core.resource.models import ResourceType
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch, Q, QuerySet
from django.views.generic import ListView

from coldfront_billing.constants import BILLING_ATTRIBUTE_NAME, BILLING_ROLE_NAME, MANAGER_ROLE_NAME
from coldfront_billing.forms import BillingSearchForm
from coldfront_billing.views.mixins import BillingAllocationPrefetchMixin, BillingListViewStateMixin


class BillingView(LoginRequiredMixin, BillingAllocationPrefetchMixin, BillingListViewStateMixin, ListView):
    model = Project
    template_name = 'billing/billing.html'
    context_object_name = 'project_list'

    @property
    def filtered_projects(self) -> QuerySet[Project]:
        search_form = BillingSearchForm(self.request.GET)
        projects = Project.objects.all()
        if search_form.is_valid():
            if username := search_form.cleaned_data.get('username'):
                projects = projects.filter(
                    Q(pi__username__icontains=username)
                    | Q(projectuser__user__username__icontains=username) & Q(projectuser__status__name='Active')
                )
            if project_title := search_form.cleaned_data.get('project_title'):
                projects = projects.filter(Q(title__icontains=project_title))
            if search_form.cleaned_data.get('no_cost_center'):
                projects = projects.filter(cost_center_assignment__isnull=True)
        return projects

    def get_queryset(self) -> QuerySet[Project]:
        ordering = self.get_ordering()
        projects = self.filtered_projects

        if not self.request.user.is_superuser:
            projects = projects.filter(
                Q(
                    projectuser__user=self.request.user,
                    projectuser__role__name__in=[BILLING_ROLE_NAME, MANAGER_ROLE_NAME],
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
                self.get_no_cost_quota_allotments_prefetch(),
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
                assignments_list = sorted(
                    assignment_obj.assignments or [],
                    key=lambda x: (x.get('department') or ''),
                )
                items = [
                    f'{row["department"]}{"." + grant if (grant := row.get("grant")) else ""}: {row["percentage"]}%'
                    for row in assignments_list
                ]
                project.cost_centers = ', '.join(items[:2]) + ' ...' if len(items) > 2 else ', '.join(items)
                project.all_cost_centers = '\n'.join(items) if items else ''
                project.assignments_json = json.dumps(assignments_list)
            except ObjectDoesNotExist:
                project.cost_centers = '-'
                project.all_cost_centers = '-'
                project.assignments_json = '[]'

        return (
            context
            | self.get_pagination_params()
            | {
                'search_form': BillingSearchForm(self.request.GET),
            }
        )
