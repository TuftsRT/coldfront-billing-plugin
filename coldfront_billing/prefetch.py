from coldfront.core.allocation.models import Allocation, AllocationAttribute
from coldfront.core.project.models import Project
from coldfront.core.resource.models import Resource, ResourceAttribute, ResourceType
from django.db.models import Prefetch, QuerySet

from coldfront_billing.constants import (
    BILLING_ATTRIBUTE_NAME,
    COST_ATTR_NAME,
    COST_ATTRIBUTE_NAME,
    NO_COST_QUOTA_DATA_ATTRIBUTE_NAME,
    QUOTA_ATTR_NAME,
    QUOTA_ATTRIBUTE_NAME,
    STORAGE_RESOURCE_ATTRIBUTE_NAME,
)
from coldfront_billing.models import NoCostQuotaAllotment
from coldfront_billing.utils import NoStorageException


def get_cost_attr_prefetch() -> Prefetch:
    """Return Prefetch for resource cost attribute."""
    return Prefetch(
        'resourceattribute_set',
        queryset=ResourceAttribute.objects.filter(resource_attribute_type__name=COST_ATTR_NAME).only(
            'resource_id', 'value', 'resource_attribute_type_id'
        ),
        to_attr=COST_ATTRIBUTE_NAME,
    )


def get_paid_storage_resources_prefetch(storage_type_id: int) -> Prefetch:
    """Return Prefetch for paid Storage resources with cost attribute."""
    return Prefetch(
        'resources',
        queryset=Resource.objects.filter(
            resource_type_id=storage_type_id,
            requires_payment=True,
        ).prefetch_related(get_cost_attr_prefetch()),
        to_attr=STORAGE_RESOURCE_ATTRIBUTE_NAME,
    )


def get_quota_attr_prefetch() -> Prefetch:
    """Return Prefetch for allocation quota attribute."""
    return Prefetch(
        'allocationattribute_set',
        queryset=AllocationAttribute.objects.filter(allocation_attribute_type__name=QUOTA_ATTR_NAME).only(
            'allocation_id', 'value'
        ),
        to_attr=QUOTA_ATTRIBUTE_NAME,
    )


def get_no_cost_quota_allotments_prefetch() -> Prefetch:
    return Prefetch(
        'no_cost_quota_allotments',
        queryset=NoCostQuotaAllotment.objects.select_related('no_cost_quota').only(
            'id',
            'allocation_id',
            'amount',
            'no_cost_quota__units',
        ),
        to_attr=NO_COST_QUOTA_DATA_ATTRIBUTE_NAME,
    )


def get_projects_prefetch(projects: QuerySet[Project]) -> QuerySet[Project, Project]:
    if not (storage_type := ResourceType.objects.only('id').filter(name='Storage').first()):
        raise NoStorageException()

    # Restrict to only projects that actually have paid Storage allocations
    projects = projects.filter(
        allocation__resources__resource_type_id=storage_type.id,
        allocation__resources__requires_payment=True,
    ).distinct()

    allocations_prefetch = Prefetch(
        'allocation_set',
        queryset=Allocation.objects.filter(
            resources__resource_type_id=storage_type.id,
            resources__requires_payment=True,
            status__name='Active',
        )
        .distinct()
        .prefetch_related(
            get_quota_attr_prefetch(),
            get_paid_storage_resources_prefetch(storage_type.id),
            get_no_cost_quota_allotments_prefetch(),
        ),
        to_attr=BILLING_ATTRIBUTE_NAME,
    )
    return projects.select_related('pi', 'status').prefetch_related(allocations_prefetch, 'cost_center_assignment')
