from django.db.models import Prefetch, Q, QuerySet

from coldfront.core.allocation.models import Allocation, AllocationAttribute
from coldfront.core.project.models import Project, ProjectUser
from coldfront.core.resource.models import Resource, ResourceAttribute, ResourceType

from .constants import (
    ALLOTMENTS_ATTRIBUTE_NAME,
    BILLING_ATTRIBUTE_NAME,
    BILLING_ROLE_NAME,
    COST_ATTR_NAME,
    COST_ATTRIBUTE_NAME,
    MANAGER_ROLE_NAME,
    NO_COST_QUOTA_TYPE_ATTR_NAME,
    QUOTA_ATTR_NAME,
    QUOTA_ATTRIBUTE_NAME,
    STORAGE_RESOURCE_ATTRIBUTE_NAME,
)
from .enums import AllocationStatus, ProjectStatus
from .models import NoCostQuota, NoCostQuotaAllotment
from .utils import NoStorageException


def get_cost_attr_prefetch() -> Prefetch:
    """Return Prefetch for resource cost attribute."""
    return Prefetch(
        "resourceattribute_set",
        queryset=ResourceAttribute.objects.filter(resource_attribute_type__name=COST_ATTR_NAME).only(
            "resource_id", "value", "resource_attribute_type_id"
        ),
        to_attr=COST_ATTRIBUTE_NAME,
    )


def get_paid_storage_resources_prefetch(storage_type_id: int) -> Prefetch:
    """Return Prefetch for paid Storage resources with cost attribute."""
    return Prefetch(
        "resources",
        queryset=Resource.objects.filter(
            resource_type_id=storage_type_id,
            requires_payment=True,
        ).prefetch_related(get_cost_attr_prefetch()),
        to_attr=STORAGE_RESOURCE_ATTRIBUTE_NAME,
    )


def get_quota_attr_prefetch() -> Prefetch:
    """Return Prefetch for allocation quota attribute."""
    return Prefetch(
        "allocationattribute_set",
        queryset=AllocationAttribute.objects.filter(allocation_attribute_type__name=QUOTA_ATTR_NAME).only(
            "allocation_id", "value"
        ),
        to_attr=QUOTA_ATTRIBUTE_NAME,
    )


def get_no_cost_quota_allotments_prefetch() -> Prefetch:
    return Prefetch(
        "no_cost_quota_allotments",
        queryset=NoCostQuotaAllotment.objects.select_related("no_cost_quota").only(
            "id",
            "allocation_id",
            "amount_tb",
            "no_cost_quota_id",
            "no_cost_quota__user_id",
            "no_cost_quota__units",
        ),
        to_attr=ALLOTMENTS_ATTRIBUTE_NAME,
    )


def get_projects_prefetch(projects: QuerySet[Project]) -> QuerySet[Project, Project]:
    if not (storage_type := ResourceType.objects.only("id").filter(name="Storage").first()):
        raise NoStorageException()

    # Restrict to only projects that actually have paid Storage allocations
    projects = projects.filter(
        allocation__resources__resource_type_id=storage_type.id,
        allocation__resources__requires_payment=True,
    ).distinct()

    allocations_prefetch = Prefetch(
        "allocation_set",
        queryset=Allocation.objects.filter(
            resources__resource_type_id=storage_type.id,
            resources__requires_payment=True,
            status__name=AllocationStatus.ACTIVE,
        )
        .distinct()
        .prefetch_related(
            get_quota_attr_prefetch(),
            get_paid_storage_resources_prefetch(storage_type.id),
            get_no_cost_quota_allotments_prefetch(),
        ),
        to_attr=BILLING_ATTRIBUTE_NAME,
    )
    return projects.select_related("pi", "status").prefetch_related(allocations_prefetch, "cost_center_assignment")


def get_filtered_allocations_prefetch(quota: NoCostQuota) -> QuerySet[Allocation]:
    quota_owner = quota.user
    storage_type = ResourceType.objects.only("id").filter(name="Storage").first()

    if not storage_type:
        return Allocation.objects.none()

    allocations = Allocation.objects.filter(
        resources__resource_type_id=storage_type.id,
        resources__requires_payment=True,
        resources__resourceattribute__resource_attribute_type__name=NO_COST_QUOTA_TYPE_ATTR_NAME,
        resources__resourceattribute__value=quota.quota_type,
        project__in=Project.objects.filter(
            Q(pi=quota_owner)
            | Q(
                projectuser__user=quota_owner,
                projectuser__role__name__in=[BILLING_ROLE_NAME, MANAGER_ROLE_NAME],
                projectuser__status__name=ProjectStatus.ACTIVE,
            )
        ),
    ).distinct()

    return (
        allocations.select_related("project", "project__pi", "status")
        .prefetch_related(
            "resources",
            get_paid_storage_resources_prefetch(storage_type.id),
            get_quota_attr_prefetch(),
            get_no_cost_quota_allotments_prefetch(),
        )
        .order_by("project__title", "pk")
    )


def get_billing_visible_projects_query(username: str) -> Q:
    """Q object matching projects a username can see billing data for: projects
    they are PI of, plus projects where they hold an active Billing/Manager role.
    Mirrors the access check in has_billing_perm()."""
    return Q(pi__username=username) | Q(
        projectuser__user__username=username,
        projectuser__role__name__in=[BILLING_ROLE_NAME, MANAGER_ROLE_NAME],
        projectuser__status__name=ProjectStatus.ACTIVE,
    )


def is_paid_storage_allocation(allocation: Allocation) -> bool:
    return allocation.resources.filter(
        resource_type__name="Storage",
        requires_payment=True,
    ).exists()


def has_billing_perm(user) -> bool:
    """
    Check if the user has billing permissions for ANY active or archived projects.
    Not to be used for checking billing permissions for a specific project; use has_billing_perm_for_project() instead.
    """
    allowed_proj_statuses = (ProjectStatus.ACTIVE, ProjectStatus.ARCHIVED)
    is_manager = ProjectUser.objects.filter(
        user=user,
        project__status__name__in=allowed_proj_statuses,
        role__name__in=[BILLING_ROLE_NAME, MANAGER_ROLE_NAME],
        status__name=ProjectStatus.ACTIVE,
    ).exists()
    is_pi = Project.objects.filter(pi=user, status__name__in=allowed_proj_statuses).exists()
    return is_manager or is_pi


def has_billing_perm_for_project(user, project: Project) -> bool:
    """
    Check if the user has billing permissions for a specific project.
    The user must be either the PI of the project or hold an active Billing/Manager role in the project.
    """
    if project.pi == user:
        return True
    return ProjectUser.objects.filter(
        user=user,
        project=project,
        role__name__in=[BILLING_ROLE_NAME, MANAGER_ROLE_NAME],
        status__name=ProjectStatus.ACTIVE,
    ).exists()


def can_apply_no_cost_quota(user, project: Project) -> bool:
    """Whether the user may apply a no-cost quota to an allocation on the project: billing staff, or the PI or a
    Billing or Manager member of the project."""
    return user.has_perm("allocation.can_view_all_allocations") or has_billing_perm_for_project(user, project)


def has_no_cost_quota_permission(user, no_cost_quota) -> bool:
    """
    Check if the user has permission to use a specific no-cost quota.
    The user must be either the owner of the quota or hold an active Billing/Manager role in a project owned by the quota's owner.
    """
    if no_cost_quota.user == user:
        return True
    ncq_owner_projects = ProjectUser.objects.filter(
        project__pi=no_cost_quota.user,
        project__status__name=ProjectStatus.ACTIVE,
        user=user,
        role__name__in=[BILLING_ROLE_NAME, MANAGER_ROLE_NAME],
        status__name=ProjectStatus.ACTIVE,
    )
    return ncq_owner_projects.exists()
