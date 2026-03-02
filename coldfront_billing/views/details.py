from typing import Any, Dict

from coldfront.core.allocation.models import Allocation
from coldfront.core.project.models import Project
from coldfront.core.resource.models import ResourceType
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView

from coldfront_billing.filters import get_allocation_ordering

from .mixins import PAGINATE_BY, BillingAllocationPrefetchMixin


class BillingDetailsView(LoginRequiredMixin, BillingAllocationPrefetchMixin, DetailView):
    """Project billing details view showing all allocations for a project."""

    model = Project
    template_name = 'billing/billing_details.html'
    context_object_name = 'project'
    pk_url_kwarg = 'project_id'
    paginate_by = PAGINATE_BY

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
        key, reverse = get_allocation_ordering(self.request.GET)
        allocations = sorted(allocations, key=key, reverse=reverse)

        request_get = self.request.GET

        paginator = Paginator(allocations, self.paginate_by)
        page_number = request_get.get('page', 1)
        page_obj = paginator.get_page(page_number)

        return (
            context
            | self.get_view_params(request_get)
            | {
                'total_cost': sum(a.total_cost for a in allocations),
                'allocations': page_obj.object_list,
                'page_obj': page_obj,
                'is_paginated': page_obj.has_other_pages(),
            }
        )
