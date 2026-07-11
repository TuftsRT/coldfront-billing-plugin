from typing import Any, Dict

from coldfront.core.allocation.models import Allocation
from coldfront.core.project.models import Project
from coldfront.core.resource.models import ResourceType
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView

from coldfront_billing.constants import BILLING_ROLE_NAME, MANAGER_ROLE_NAME
from coldfront_billing.data.billing import create_billing_allocations
from coldfront_billing.enums import AllocationStatus, ProjectStatus
from coldfront_billing.prefetch import (
    get_no_cost_quota_allotments_prefetch,
    get_paid_storage_resources_prefetch,
    get_quota_attr_prefetch,
)
from coldfront_billing.views.mixins import BillingListViewStateMixin


class BillingDetailsView(LoginRequiredMixin, BillingListViewStateMixin, DetailView):
    """Project billing details view showing all allocations for a project."""

    model = Project
    template_name = 'billing/billing_details.html'
    context_object_name = 'project'
    pk_url_kwarg = 'project_id'

    def check_permission(self, project: Project) -> bool:
        user = self.request.user
        if user.is_superuser:
            return True
        return (
            project.projectuser_set.filter(
                user=user,
                role__name__in=[BILLING_ROLE_NAME, MANAGER_ROLE_NAME],
                status__name=ProjectStatus.ACTIVE,
            ).exists()
            or project.pi_id == user.id
        )

    def get(self, request, *args, **kwargs):
        project = get_object_or_404(Project, id=kwargs['project_id'])
        if not self.check_permission(project):
            messages.error(request, 'You do not have permission to view this project.')
            return redirect('billing_index')
        return super().get(request, *args, **kwargs)

    def get_queryset(self) -> QuerySet[Project]:
        return Project.objects.filter(id=self.kwargs['project_id'])

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        project = self.object

        if not (storage_type := ResourceType.objects.only('id').filter(name='Storage').first()):
            context['allocations'] = []
            context['total_cost'] = 0.0
            return context

        allocation_objs = (
            Allocation.objects.filter(
                project=project,
                resources__resource_type_id=storage_type.id,
                resources__requires_payment=True,
                status__name=AllocationStatus.ACTIVE,
            )
            .distinct()
            .select_related('project', 'project__pi', 'status')
            .prefetch_related(
                get_quota_attr_prefetch(),
                get_paid_storage_resources_prefetch(storage_type.id),
                get_no_cost_quota_allotments_prefetch(),
            )
        )
        allocations = create_billing_allocations([a for a in allocation_objs])
        key, reverse = self.get_object_ordering()
        allocations = sorted(allocations, key=key, reverse=reverse)

        return (
            context
            | self.get_extended_pagination_params(allocations)
            | {
                'total_cost': round(sum(a.total_cost for a in allocations), 2),
            }
        )
