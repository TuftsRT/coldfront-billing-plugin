import logging
import random

from coldfront.core.project.models import Project
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.views.generic import ListView

logger = logging.getLogger(__name__)


class BillingView(LoginRequiredMixin, ListView):
    model = Project
    template_name = 'billing/billing.html'
    context_object_name = 'project_list'

    def get_queryset(self):
        order_by = self.request.GET.get('order_by', 'id')
        direction = self.request.GET.get('direction', 'asc')

        if direction == 'des':
            order_by = '-' + order_by

        projects = Project.objects.prefetch_related(
            'pi',
            'status',
        )

        if not self.request.user.is_superuser:
            projects = projects.filter(
                projectuser__user=self.request.user,
                projectuser__role__name='Billing',
                projectuser__status__name='Active',
            )

        return projects.order_by(order_by).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Count projects from the list to avoid duplicate query
        context['projects_count'] = len(context['project_list'])

        project_list = context.get('project_list', [])
        for project in project_list:
            # Generate random cost between 100-1000
            project.cost = f'${random.randint(100, 1000)}'
            # Cost centers currently set to '-'
            project.cost_centers = '-'

        return context


def b_link(request):
    return HttpResponse('<h1>This is the B-Link Page</h1>')
