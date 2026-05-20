from urllib.parse import urlparse

from coldfront.core.allocation.models import (
    Allocation,
    AllocationAttribute,
    AllocationAttributeType,
    AllocationPermission,
)
from coldfront.core.allocation.views import AllocationChangeView as ColdfrontAllocationChangeView
from coldfront.core.allocation.views import AllocationCreateView as ColdfrontAllocationCreateView
from coldfront.core.project.models import Project
from coldfront.core.resource.models import ResourceType
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import FormView

from coldfront_billing.billing import default_cost, default_quota
from coldfront_billing.constants import (
    ALLOCATION_QUOTA_ATTRIBUTE_NAME,
    NO_COST_QUOTA_TYPE_ATTR_NAME,
    QUOTA_ATTR_NAME,
    STORAGE_RESOURCE_ATTRIBUTE_NAME,
)
from coldfront_billing.data.billing import BillingAllocation
from coldfront_billing.forms import AllocationDetailsForm
from coldfront_billing.models import CostCenterAssignment
from coldfront_billing.prefetch import (
    get_no_cost_quota_allotments_prefetch,
    get_paid_storage_resources_prefetch,
    get_quota_attr_prefetch,
    is_paid_storage_allocation,
)
from coldfront_billing.utils import first_or_none
from coldfront_billing.views.no_cost_quota.common import quota_with_remaining


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

        # Redirect to update_allocation_details page for paid storage allocations
        if allocation and is_paid_storage_allocation(allocation):
            return redirect(
                'update_allocation_details',
                pk=allocation.pk,
            )

        return redirect_response


class UpdateAllocationDetailsView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """View for update storage quota to complete a storage allocation request."""

    allocation: Allocation
    has_cost_center: bool
    form_class = AllocationDetailsForm
    template_name = 'allocation/update_details.html'

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
            del form.fields['grant']
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
        grant = form.cleaned_data.get('grant')

        try:
            attr_type = AllocationAttributeType.objects.get(name=QUOTA_ATTR_NAME)
            self.allocation.allocationattribute_set.create(
                allocation_attribute_type=attr_type,
                value=str(quota),
            )

            if apply_quota_value := self.request.POST.get('apply_allocation_quota', '').strip():
                try:
                    apply_attr_type = AllocationAttributeType.objects.get(name=ALLOCATION_QUOTA_ATTRIBUTE_NAME)
                except AllocationAttributeType.DoesNotExist:
                    messages.warning(
                        self.request,
                        'Quota application preference could not be saved. Please contact support.',
                    )
                else:
                    self.allocation.allocationattribute_set.create(
                        allocation_attribute_type=apply_attr_type,
                        value=apply_quota_value,
                    )

            if cost_center is not None:
                cost_center_assignment, _ = CostCenterAssignment.objects.get_or_create(
                    project=self.allocation.project,
                    defaults={'assignments': []},
                )

                assignment = {
                    'department': cost_center.name,
                    'percentage': 100,
                }

                if grant:
                    assignment.update({'grant': grant.name})

                cost_center_assignment.assignments = [assignment]

                cost_center_assignment.save()
        except AllocationAttributeType.DoesNotExist:
            messages.error(
                self.request,
                'Unable to save quota. Please contact support.',
            )
            return redirect('allocation-detail', pk=self.allocation.pk)
        else:
            if cost_center is not None:
                partial = f'.{grant}' if grant else ''
                msg = (
                    f'Storage quota of {quota} TB has been set with 100% cost assigned to '
                    f'{cost_center.name}{partial}. Your allocation request is complete.'
                )
            else:
                msg = f'Storage quota of {quota} TB has been set. Your allocation request is complete.'
            messages.success(self.request, msg)
            return redirect(reverse('project-detail', kwargs={'pk': self.allocation.project_id}))


class AllocationCostPreviewView(LoginRequiredMixin, UserPassesTestMixin, View):
    """JSON endpoint: estimated total cost for a storage quota (TB) before completing the allocation."""

    def test_func(self):
        allocation = get_object_or_404(Allocation, pk=self.kwargs['pk'])
        if self.request.user.has_perm('allocation.can_view_all_allocations'):
            return True
        return allocation.has_perm(self.request.user, AllocationPermission.USER)

    def get(self, request, *args, **kwargs):
        try:
            quota_tb = float(request.GET['quota_in_terabyte'])
        except (KeyError, TypeError, ValueError):
            return JsonResponse({'error': 'quota_in_terabyte is required and must be a number.'}, status=400)
        if quota_tb < 0:
            return JsonResponse({'error': 'quota_in_terabyte must be zero or positive.'}, status=400)

        storage_type = ResourceType.objects.only('id').filter(name='Storage').first()
        if not storage_type:
            return JsonResponse({'error': 'Storage resource type is not configured.'}, status=500)

        allocation = get_object_or_404(
            Allocation.objects.select_related('project', 'status').prefetch_related(
                get_paid_storage_resources_prefetch(storage_type.id),
                get_no_cost_quota_allotments_prefetch(),
                get_quota_attr_prefetch(),
            ),
            pk=kwargs['pk'],
        )

        remaining_quota = 0
        quota_id = None
        storage_resource = first_or_none(getattr(allocation, STORAGE_RESOURCE_ATTRIBUTE_NAME, []))

        if storage_resource:
            no_cost_quota_att = storage_resource.resourceattribute_set.filter(
                resource_attribute_type__name=NO_COST_QUOTA_TYPE_ATTR_NAME
            ).first()
            if no_cost_quota_att:
                allocation_user = self.request.user
                quota_user = allocation_user if not allocation_user.is_superuser else allocation.project.pi

                no_cost_quota = quota_with_remaining.filter(user=quota_user, quota_type=no_cost_quota_att.value).first()
                if no_cost_quota and no_cost_quota.remaining_normalized > 0:
                    remaining_quota = no_cost_quota.remaining_normalized
                    quota_id = no_cost_quota.id

        billing = BillingAllocation.parse(allocation, default_quota, default_cost, quota_tb)

        response = {
            'total_cost': billing.total_cost,
            'quota_cost': billing.calculate_cost(quota_tb),
            'cost_per_tb': billing.cost_per_tb,
            'quota_tb': quota_tb,
        }

        if quota_id:
            reduced_cost, applied_quota_amount = billing.get_predicted_cost(remaining_quota)
            response.update(
                {
                    'quota_id': quota_id,
                    'applied_quota': applied_quota_amount,
                    'reduced_cost': reduced_cost,
                }
            )

        return JsonResponse(response)


class BillingAllocationChangeView(ColdfrontAllocationChangeView):
    """
    ColdFront ``AllocationChangeView`` plus ``apply_allocation_quota`` POST (same as solution 1:
    extend the allocation-change handler to set ``ALLOCATION_QUOTA_ATTRIBUTE_NAME`` on success).
    """

    def post(self, request, *args, **kwargs):
        apply_quota_raw = request.POST.get('apply_allocation_quota', '').strip()
        pk = self.kwargs.get('pk')
        response = super().post(request, *args, **kwargs)
        if apply_quota_raw and pk is not None and self._is_successful_change_submission(response, pk):
            try:
                apply_attr_type = AllocationAttributeType.objects.get(name=ALLOCATION_QUOTA_ATTRIBUTE_NAME)
            except AllocationAttributeType.DoesNotExist:
                messages.warning(
                    request,
                    'Quota application preference could not be saved. Please contact support.',
                )
            else:
                allocation = get_object_or_404(Allocation, pk=pk)
                AllocationAttribute.objects.update_or_create(
                    allocation=allocation,
                    allocation_attribute_type=apply_attr_type,
                    defaults={'value': apply_quota_raw},
                )
        return response

    @staticmethod
    def _is_successful_change_submission(response: HttpResponse, allocation_pk: int | str) -> bool:
        if not isinstance(response, HttpResponseRedirect):
            return False
        expected = reverse('allocation-detail', kwargs={'pk': allocation_pk})
        location = response.url
        path = urlparse(location).path if location.startswith(('http://', 'https://')) else location
        return path.rstrip('/') == expected.rstrip('/')
