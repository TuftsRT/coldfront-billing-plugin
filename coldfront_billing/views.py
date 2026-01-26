import logging
import random

from coldfront.core.project.forms import ProjectSearchForm
from coldfront.core.project.models import Project
from coldfront.core.utils.common import import_from_settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponse
from django.views.generic import ListView

logger = logging.getLogger(__name__)
PROJECT_INSTITUTION_EMAIL_MAP = import_from_settings('PROJECT_INSTITUTION_EMAIL_MAP', False)


class BillingView(LoginRequiredMixin, ListView):
    model = Project
    template_name = 'billing/billing.html'
    prefetch_related = [
        'pi',
        'status',
        'field_of_science',
    ]
    context_object_name = 'project_list'
    paginate_by = 25

    def get_queryset(self):
        order_by = self.request.GET.get('order_by', 'id')
        direction = self.request.GET.get('direction', 'asc')
        if order_by != 'name':
            if direction == 'asc':
                direction = ''
            if direction == 'des':
                direction = '-'
            order_by = direction + order_by

        projects = (
            Project.objects.prefetch_related(
                'pi',
                'field_of_science',
                'status',
            )
            .filter(
                Q(
                    status__name__in=[
                        'New',
                        'Active',
                    ]
                )
                & Q(projectuser__user=self.request.user)
                & Q(projectuser__status__name='Active')
            )
            .order_by(order_by)
        )

        return projects.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        projects_count = self.get_queryset().count()
        context['projects_count'] = projects_count

        project_search_form = ProjectSearchForm(self.request.GET)
        if project_search_form.is_valid():
            context['project_search_form'] = project_search_form
            data = project_search_form.cleaned_data
            filter_parameters = ''
            for key, value in data.items():
                if value:
                    if isinstance(value, list):
                        for ele in value:
                            filter_parameters += '{}={}&'.format(key, ele)
                    else:
                        filter_parameters += '{}={}&'.format(key, value)
            context['project_search_form'] = project_search_form
        else:
            filter_parameters = None
            context['project_search_form'] = ProjectSearchForm()

        order_by = self.request.GET.get('order_by')
        if order_by:
            direction = self.request.GET.get('direction')
            filter_parameters_with_order_by = filter_parameters + 'order_by=%s&direction=%s&' % (order_by, direction)
        else:
            filter_parameters_with_order_by = filter_parameters

        if filter_parameters:
            context['expand_accordion'] = 'show'

        context['filter_parameters'] = filter_parameters
        context['filter_parameters_with_order_by'] = filter_parameters_with_order_by
        context['PROJECT_INSTITUTION_EMAIL_MAP'] = PROJECT_INSTITUTION_EMAIL_MAP

        # Add cost and cost centers to each project in the paginated list
        project_list = context.get('project_list')
        if project_list:
            for project in project_list:
                # Generate random cost between 100-1000
                project.cost = f'${random.randint(100, 1000)}'
                # Cost centers currently set to '-'
                project.cost_centers = '-'

        return context


def b_link(request):
    return HttpResponse('<h1>This is the B-Link Page</h1>')
