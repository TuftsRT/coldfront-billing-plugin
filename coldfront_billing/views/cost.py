import logging

from coldfront.core.project.models import Project
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from coldfront_billing.constants import BILLING_ROLE_NAME, MANAGER_ROLE_NAME
from coldfront_billing.data import ApiErrorResponseDTO, ApiSuccessResponseDTO
from coldfront_billing.enum import ProjectStatus
from coldfront_billing.forms import CostCenterAssignmentForm
from coldfront_billing.models import CostCenter, CostCenterAssignment

logger = logging.getLogger('CostCenterView')


class CostCenterAssignmentUpdateView(LoginRequiredMixin, View):
    """Updating cost center assignments View."""

    def check_permission(self, project: Project) -> bool:
        if self.request.user.is_superuser:
            return True

        return project.projectuser_set.filter(
            user=self.request.user,
            role__name__in=[BILLING_ROLE_NAME, MANAGER_ROLE_NAME],
            status__name=ProjectStatus.ACTIVE,
        ).exists()

    def post(self, request: HttpRequest) -> JsonResponse:
        form = CostCenterAssignmentForm(request.POST)

        if not form.is_valid():
            error_response = ApiErrorResponseDTO(errors=form.errors)
            return JsonResponse(error_response.to_dict(), status=400)

        project_id = form.cleaned_data['project_id']
        assignments_data = form.cleaned_data['assignments']

        try:
            project = get_object_or_404(Project, id=project_id)

            if not self.check_permission(project):
                error_response = ApiErrorResponseDTO(error='You do not have permission to modify this project.')
                return JsonResponse(error_response.to_dict(), status=403)

            cost_center_assignment, _ = CostCenterAssignment.objects.get_or_create(
                project=project,
                defaults={'assignments': []},
            )

            cost_center_assignment.assignments = assignments_data

            cost_center_assignment.save()

            success_response = ApiSuccessResponseDTO(
                message='Cost center assignment updated successfully.', assignments=cost_center_assignment.assignments
            )
            return JsonResponse(success_response.to_dict())

        except Exception as cause:
            logger.error(f'Error updating cost center assignment: {str(cause)}')
            error_response = ApiErrorResponseDTO(error='An error occurred while updating the cost center assignment.')
            return JsonResponse(error_response.to_dict(), status=400)


class CostCenterAutocompleteView(LoginRequiredMixin, View):
    def get(self, request):
        query = request.GET.get('q', '').strip()
        cc_type = request.GET.get('type', 'department')

        if len(query) < 3:
            return JsonResponse({'results': []})

        results = list(
            CostCenter.objects.filter(name__istartswith=query, cost_center_type=cc_type)
            .values_list('name', flat=True)
            .distinct()
            .order_by('name')[:10]
        )

        return JsonResponse({'results': results})
