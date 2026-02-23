from coldfront.core.allocation.models import Allocation, AllocationAttributeType, AllocationPermission
from coldfront.core.allocation.views import AllocationCreateView as ColdfrontAllocationCreateView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import FormView

from coldfront_billing.constants import QUOTA_ATTR_NAME
from coldfront_billing.forms import StorageQuotaForm


class AllocationCreateView(ColdfrontAllocationCreateView):
    """Allocation create view override that redirects to quota page for paid storage allocations."""

    def form_valid(self, form):
        redirect_response = super().form_valid(form)
        allocation: Allocation = self.object

        # Redirect to update-storage-quota page for paid storage allocations
        if allocation.resources.filter(
            resource_type__name='Storage',
            requires_payment=True,
        ).exists():
            return redirect(
                'update-storage-quota',
                pk=allocation.pk,
            )

        return redirect_response


class UpdateStorageQuotaView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """View for update storage quota to complete a storage allocation request."""

    form_class = StorageQuotaForm
    template_name = 'billing/update_storage_quota.html'

    def test_func(self):
        allocation = get_object_or_404(Allocation, pk=self.kwargs['pk'])
        if self.request.user.has_perm('allocation.can_view_all_allocations'):
            return True
        return allocation.has_perm(self.request.user, AllocationPermission.USER)

    def dispatch(self, request, *args, **kwargs):
        self.allocation = get_object_or_404(
            Allocation.objects.select_related('project', 'status').prefetch_related('resources__resource_type'),
            pk=kwargs['pk'],
        )
        if not self.allocation.resources.filter(
            resource_type__name='Storage',
            requires_payment=True,
        ).exists():
            return redirect('allocation-detail', pk=self.allocation.pk)
        if self.allocation.allocationattribute_set.filter(
            allocation_attribute_type__name=QUOTA_ATTR_NAME,
        ).exists():
            messages.info(request, 'Storage quota is already set for this allocation.')
            return redirect(self.allocation.project.get_absolute_url())
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['allocation'] = self.allocation
        context['resource'] = self.allocation.get_parent_resource
        return context

    def form_valid(self, form):
        quota = form.cleaned_data['quota_in_terabyte']

        try:
            attr_type = AllocationAttributeType.objects.get(name=QUOTA_ATTR_NAME)
            self.allocation.allocationattribute_set.create(
                allocation_attribute_type=attr_type,
                value=str(quota),
            )
        except AllocationAttributeType.DoesNotExist:
            messages.error(
                self.request,
                'Unable to save quota. Please contact support.',
            )
            return redirect('allocation-detail', pk=self.allocation.pk)
        else:
            messages.success(
                self.request,
                f'Storage quota of {quota} TB has been set. Your allocation request is complete.',
            )
            return redirect(self.allocation.project.get_absolute_url())
