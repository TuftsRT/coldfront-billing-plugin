from coldfront.core.allocation.models import Allocation, AllocationAttributeType, AllocationPermission
from coldfront.core.allocation.views import AllocationCreateView as ColdfrontAllocationCreateView
from coldfront.core.project.models import Project
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import FormView

from coldfront_billing.constants import QUOTA_ATTR_NAME
from coldfront_billing.forms import AllocationDetailsForm
from coldfront_billing.models import CostCenterAssignment


def project_has_cost_center_assignment(project: Project) -> bool:
    """Return True if the project already has cost centers assigned."""
    try:
        assignments = project.cost_center_assignment.assignments
        return bool(assignments)
    except CostCenterAssignment.DoesNotExist:
        return False


class AllocationCreateView(ColdfrontAllocationCreateView):
    """Allocation create view override that redirects to quota page for paid storage allocations."""

    def form_valid(self, form):
        redirect_response = super().form_valid(form)
        allocation = Allocation.objects.filter(project_id=self.kwargs['project_pk']).order_by('-pk').first()

        # Redirect to update-allocation-details page for paid storage allocations
        if (
            allocation
            and allocation.resources.filter(
                resource_type__name='Storage',
                requires_payment=True,
            ).exists()
        ):
            return redirect(
                'update-allocation-details',
                pk=allocation.pk,
            )

        return redirect_response


class UpdateAllocationDetailsView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """View for update storage quota to complete a storage allocation request."""

    allocation: Allocation
    has_cost_center: bool
    form_class = AllocationDetailsForm
    template_name = 'billing/update_allocation_details.html'

    def test_func(self):
        allocation = get_object_or_404(Allocation, pk=self.kwargs['pk'])
        if self.request.user.has_perm('allocation.can_view_all_allocations'):
            return True
        return allocation.has_perm(self.request.user, AllocationPermission.USER)

    def dispatch(self, request, *args, **kwargs):
        self.allocation = get_object_or_404(
            Allocation.objects.select_related('project', 'project__cost_center_assignment', 'status').prefetch_related(
                'resources__resource_type'
            ),
            pk=kwargs['pk'],
        )
        self.has_cost_center = project_has_cost_center_assignment(self.allocation.project)
        if self.allocation.allocationattribute_set.filter(
            allocation_attribute_type__name=QUOTA_ATTR_NAME,
        ).exists():
            messages.info(request, 'Storage quota is already set for this allocation.')
            return redirect(reverse('project-detail', kwargs={'pk': self.allocation.project_id}))
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.has_cost_center:
            del form.fields['cost_center']
        return form

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {
            'allocation': self.allocation,
            'resource': self.allocation.get_parent_resource,
            'show_cost_center': not self.has_cost_center,
        }

    def form_valid(self, form):
        quota = form.cleaned_data['quota_in_terabyte']
        cost_center = form.cleaned_data.get('cost_center')

        try:
            attr_type = AllocationAttributeType.objects.get(name=QUOTA_ATTR_NAME)
            self.allocation.allocationattribute_set.create(
                allocation_attribute_type=attr_type,
                value=str(quota),
            )

            if cost_center is not None:
                cost_center_assignment, _ = CostCenterAssignment.objects.get_or_create(
                    project=self.allocation.project, defaults={'assignments': {}}
                )
                cost_center_assignment.assignments = {cost_center.dept_id: 100}
                cost_center_assignment.save()
        except AllocationAttributeType.DoesNotExist:
            messages.error(
                self.request,
                'Unable to save quota. Please contact support.',
            )
            return redirect('allocation-detail', pk=self.allocation.pk)
        else:
            if cost_center is not None:
                msg = (
                    f'Storage quota of {quota} TB has been set with 100% cost assigned to '
                    f'{cost_center.dept_id}. Your allocation request is complete.'
                )
            else:
                msg = f'Storage quota of {quota} TB has been set. Your allocation request is complete.'
            messages.success(self.request, msg)
            return redirect(reverse('project-detail', kwargs={'pk': self.allocation.project_id}))
