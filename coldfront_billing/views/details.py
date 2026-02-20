import logging
from typing import Any, Dict

from coldfront.core.allocation.models import Allocation
from coldfront.core.project.models import Project
from coldfront.core.resource.models import ResourceType
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView

from .mixins import BillingAllocationPrefetchMixin

logger = logging.getLogger('BillingDetailsView')


class BillingDetailsView(LoginRequiredMixin, BillingAllocationPrefetchMixin, DetailView):
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
                role__name='Billing',
                status__name='Active',
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
        # project_id = project.id

        # session_allocations = self.request.session.get('billing_allocations') or {}
        # if project_id in session_allocations:
        #     logger.info('using billing allocations from session')
        #     allocations = session_allocations[project_id]
        #     context['allocations'] = allocations
        #     context['total_cost'] = sum(a['total_cost'] for a in allocations)
        #     return context
        # logger.info('fallback: fetching allocations from DB')

        # Fallback: fetch from DB (e.g. direct URL, bookmarked link)
        if not (storage_type := ResourceType.objects.only('id').filter(name='Storage').first()):
            context['allocations'] = []
            context['total_cost'] = 0
            return context

        allocation_objs = (
            Allocation.objects.filter(
                project=project,
                resources__resource_type_id=storage_type.id,
                resources__requires_payment=True,
                status__name='Active',
            )
            .distinct()
            .select_related('project', 'project__pi', 'status')
            .prefetch_related(
                self.get_quota_attr_prefetch(),
                self.get_paid_storage_resources_prefetch(storage_type.id),
            )
        )
        allocations = self.create_billing_allocations([a for a in allocation_objs])
        logger.info(allocations)
        context['allocations'] = sorted(allocations, key=lambda a: a.allocation_id)
        context['total_cost'] = sum(a.total_cost for a in allocations)
        return context
