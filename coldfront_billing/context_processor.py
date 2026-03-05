from coldfront.core.project.models import Project, ProjectUser
from django.http import HttpRequest

from coldfront_billing.constants import BILLING_ROLE_NAME, MANAGER_ROLE_NAME

ALLOWED_PROJECT_STATUSES = ('Active', 'Archived')


def billing_role(request: HttpRequest):
    user = request.user

    if not user.is_authenticated:
        return {}

    if user.is_superuser:
        return {'has_billing_role': True}

    has_billing = ProjectUser.objects.filter(
        user=user,
        project__status__name__in=ALLOWED_PROJECT_STATUSES,
        role__name__in=[BILLING_ROLE_NAME, MANAGER_ROLE_NAME],
        status__name='Active',
    ).exists()

    is_pi = Project.objects.filter(pi=user, status__name__in=ALLOWED_PROJECT_STATUSES).exists()

    return {'has_billing_role': has_billing or is_pi}
