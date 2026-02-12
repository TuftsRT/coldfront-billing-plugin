from coldfront.core.project.models import Project, ProjectUser
from django.http import HttpRequest


def billing_role(request: HttpRequest):
    user = request.user

    if not user.is_authenticated:
        return {}

    if user.is_superuser:
        return {'has_billing_role': True}

    has_billing = ProjectUser.objects.filter(
        user=user, project__status__name__in=('Active', 'Archived'), role__name='Billing', status__name='Active'
    ).exists()

    is_pi = Project.objects.filter(
        pi=user, status__name__in=('Active', 'Archived')
    ).exists()

    return {'has_billing_role': has_billing or is_pi}
