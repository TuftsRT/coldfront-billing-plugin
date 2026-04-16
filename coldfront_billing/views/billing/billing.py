import json
from typing import Any, Dict

from coldfront.core.project.models import Project
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, QuerySet
from django.views.generic import ListView

from coldfront_billing.billing import create_billing_allocations
from coldfront_billing.constants import BILLING_ATTRIBUTE_NAME, BILLING_ROLE_NAME, MANAGER_ROLE_NAME
from coldfront_billing.forms import BillingSearchForm
from coldfront_billing.prefetch import get_projects_prefetch
from coldfront_billing.utils import NoStorageException
from coldfront_billing.views.mixins import BillingListViewStateMixin


class BillingView(LoginRequiredMixin, BillingListViewStateMixin, ListView):
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

        try:
            return get_projects_prefetch(projects).order_by(ordering)
        except NoStorageException:
            return projects.select_related('pi', 'status').order_by(ordering)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        # Count projects from the list to avoid duplicate query
        context['projects_count'] = len(context['project_list'])

        for project in context.get('project_list', []):
            billing_allocations = create_billing_allocations([a for a in getattr(project, BILLING_ATTRIBUTE_NAME, [])])
            project_cost = sum(b.total_cost for b in billing_allocations)
            project.cost = f'${project_cost}'

            # 2. Handle Cost Center & JSON Serialization safely
            try:
                assignment_obj = project.cost_center_assignment
                assignments_list = sorted(
                    assignment_obj.assignments or [],
                    key=lambda x: (x.get('department') or ''),
                )
                items = [f'{row["department"]}: {row["percentage"]}%' for row in assignments_list]
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
