"""Mock factories for billing / quota tests (module-level to avoid pytest collecting imported Test classes)."""

from unittest.mock import Mock

from coldfront_billing.constants import (
    ALLOTMENTS_ATTRIBUTE_NAME,
    COST_ATTRIBUTE_NAME,
    QUOTA_ATTRIBUTE_NAME,
    STORAGE_RESOURCE_ATTRIBUTE_NAME,
)
from coldfront_billing.enums import AllocationStatus


def create_mock_allotment(amount, units="TB"):
    """Create a mock no-cost quota allotment object."""
    allotment = Mock()
    allotment.amount_tb = amount
    allotment.no_cost_quota = Mock()
    allotment.no_cost_quota.units = units
    return allotment


def create_mock_allocation(
    allocation_id=1,
    project_id=1,
    quota_attrs=None,
    storage_resources=None,
    project=None,
    status=None,
    end_date=None,
    no_cost_quota_data=None,
):
    """Create a mock allocation object.

    Attributes are only set when provided (truthy), so missing attributes
    trigger getattr defaults - matching real allocations without prefetched data.
    """
    spec = [
        "id",
        "project_id",
        "end_date",
        "status",
        "project",
        QUOTA_ATTRIBUTE_NAME,
        STORAGE_RESOURCE_ATTRIBUTE_NAME,
    ]
    if no_cost_quota_data:
        spec = spec + [ALLOTMENTS_ATTRIBUTE_NAME]
    allocation = Mock(spec=spec)
    allocation.id = allocation_id
    allocation.project_id = project_id
    allocation.end_date = end_date

    status_mock = Mock()
    status_mock.name = status or AllocationStatus.ACTIVE
    allocation.status = status_mock

    allocation.project = project
    setattr(allocation, QUOTA_ATTRIBUTE_NAME, quota_attrs)
    setattr(allocation, STORAGE_RESOURCE_ATTRIBUTE_NAME, storage_resources)
    if no_cost_quota_data:
        setattr(allocation, ALLOTMENTS_ATTRIBUTE_NAME, no_cost_quota_data)
    return allocation


def create_mock_storage_resource(cost_attrs=None, name="Test Storage"):
    """Create a mock storage resource object."""
    resource = Mock()
    resource.name = name
    setattr(resource, COST_ATTRIBUTE_NAME, cost_attrs)
    return resource


def create_mock_project(title="Test Project", pi=None):
    """Create a mock project object."""
    project = Mock()
    project.title = title
    project.pi = pi
    return project


def create_mock_pi(username="pi_user"):
    """Create a mock PI user object."""
    pi = Mock()
    pi.username = username
    return pi


def create_ncq_allotment(amount, units="TB", user_id=1):
    """Mock no-cost quota allotment with user_id (for PricedAllocation / engine tests)."""
    allotment = Mock()
    allotment.amount_tb = amount
    allotment.no_cost_quota = Mock()
    allotment.no_cost_quota.units = units
    allotment.no_cost_quota.user_id = user_id
    return allotment


def mock_allocation_for_priced(
    *,
    all_allotments=(),
    quota_attrs=None,
    storage_resources=None,
):
    allocation = Mock(
        spec=["id", ALLOTMENTS_ATTRIBUTE_NAME, QUOTA_ATTRIBUTE_NAME, STORAGE_RESOURCE_ATTRIBUTE_NAME],
    )
    allocation.id = 1
    allocation.all_allotments = all_allotments
    setattr(
        allocation,
        QUOTA_ATTRIBUTE_NAME,
        quota_attrs if quota_attrs is not None else [Mock(value="10")],
    )
    setattr(
        allocation,
        STORAGE_RESOURCE_ATTRIBUTE_NAME,
        [] if storage_resources is None else storage_resources,
    )
    return allocation


def storage_resource_with_cost(value):
    resource = Mock()
    setattr(resource, COST_ATTRIBUTE_NAME, [Mock(value=value)])
    return resource
