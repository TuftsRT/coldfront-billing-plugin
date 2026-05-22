from typing import List, Optional

import pytest
from coldfront.core.allocation.models import (
    Allocation,
    AllocationAttribute,
    AllocationAttributeType,
    AllocationStatusChoice,
)
from coldfront.core.allocation.models import (
    AttributeType as AllocationAttributeTypeBase,
)
from coldfront.core.field_of_science.models import FieldOfScience
from coldfront.core.project.models import (
    Project,
    ProjectStatusChoice,
    ProjectUser,
    ProjectUserRoleChoice,
    ProjectUserStatusChoice,
)
from coldfront.core.resource.models import (
    AttributeType as ResourceAttributeTypeBase,
)
from coldfront.core.resource.models import (
    Resource,
    ResourceAttribute,
    ResourceAttributeType,
    ResourceType,
)
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.test import override_settings

from coldfront_billing.constants import (
    BILLING_ROLE_NAME,
    COST_ATTR_NAME,
    MANAGER_ROLE_NAME,
    NO_COST_QUOTA_TYPE_ATTR_NAME,
    QUOTA_ATTR_NAME,
)
from coldfront_billing.enum import AllocationStatus, ProjectStatus


@pytest.fixture
def configure_urls():
    """Configure URLs for view tests."""
    with override_settings(ROOT_URLCONF='coldfront_billing.tests.conftest_urls'):
        yield


# ============================================================================
# User Fixtures
# ============================================================================


@pytest.fixture
def user(db) -> User:
    """Create a regular user."""
    return User.objects.create_user(username='testuser', email='test@example.com', password='testpass123')


@pytest.fixture
def superuser(db) -> User:
    """Create a superuser."""
    return User.objects.create_superuser(username='admin', email='admin@example.com', password='adminpass123')


@pytest.fixture
def pi_user(db) -> User:
    """Create a PI user."""
    return User.objects.create_user(username='pi_user', email='pi@example.com', password='pipass123')


# ============================================================================
# Project Status and Role Fixtures
# ============================================================================


@pytest.fixture
def project_status_active(db) -> ProjectStatusChoice:
    """Create an Active project status."""
    return ProjectStatusChoice.objects.get_or_create(name='Active')[0]


@pytest.fixture
def project_status_archived(db) -> ProjectStatusChoice:
    """Create an Archived project status."""
    return ProjectStatusChoice.objects.get_or_create(name=ProjectStatus.ARCHIVED)[0]


@pytest.fixture
def project_status_new(db) -> ProjectStatusChoice:
    """Create a New project status."""
    return ProjectStatusChoice.objects.get_or_create(name='New')[0]


def get_or_create_project_role(role_name: str) -> ProjectUserRoleChoice:
    """Get or create a project user role by name."""
    return ProjectUserRoleChoice.objects.get_or_create(name=role_name)[0]


@pytest.fixture
def billing_role_choice(db) -> ProjectUserRoleChoice:
    """Create the Billing role."""
    return get_or_create_project_role(BILLING_ROLE_NAME)


@pytest.fixture
def billing_role(billing_role_choice: ProjectUserRoleChoice) -> ProjectUserRoleChoice:
    """Alias for billing_role_choice for backward compatibility."""
    return billing_role_choice


@pytest.fixture
def manager_role(db) -> ProjectUserRoleChoice:
    """Create the Manager role."""
    return get_or_create_project_role(MANAGER_ROLE_NAME)


@pytest.fixture
def project_user_status_active(db) -> ProjectUserStatusChoice:
    """Create an Active project user status."""
    return ProjectUserStatusChoice.objects.get_or_create(name='Active')[0]


@pytest.fixture
def project_user_status_inactive(db) -> ProjectUserStatusChoice:
    """Create an Inactive project user status."""
    return ProjectUserStatusChoice.objects.get_or_create(name='Inactive')[0]


# ============================================================================
# Project Fixtures
# ============================================================================


@pytest.fixture
def field_of_science(db) -> FieldOfScience:
    """Create a FieldOfScience for projects."""
    return FieldOfScience.objects.get_or_create(description='Test Field of Science', defaults={'is_selectable': True})[
        0
    ]


@pytest.fixture
def project(pi_user: User, project_status_active: ProjectStatusChoice, field_of_science: FieldOfScience, db) -> Project:
    """Create a test project."""
    return Project.objects.create(
        title='Test Project',
        pi=pi_user,
        status=project_status_active,
        field_of_science=field_of_science,
    )


def _create_project_with_role_user(
    project: Project,
    user: User,
    role: ProjectUserRoleChoice,
    project_user_status_active: ProjectUserStatusChoice,
    storage_resource_type: ResourceType,
    allocation_status_active: AllocationStatusChoice,
    cost_attribute_type: ResourceAttributeType,
    quota_attribute_type: AllocationAttributeType,
) -> Project:
    """Create a project with a user having the given role and Storage allocation."""
    ProjectUser.objects.create(
        project=project,
        user=user,
        role=role,
        status=project_user_status_active,
    )

    add_storage_allocation_to_project(
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    )

    return project


@pytest.fixture
def project_with_billing_user(
    user: User,
    project: Project,
    billing_role: ProjectUserRoleChoice,
    project_user_status_active: ProjectUserStatusChoice,
    storage_resource_type: ResourceType,
    allocation_status_active: AllocationStatusChoice,
    cost_attribute_type: ResourceAttributeType,
    quota_attribute_type: AllocationAttributeType,
    db,
) -> Project:
    """Create a project with a user having Billing role and Storage allocation."""
    return _create_project_with_role_user(
        project,
        user,
        billing_role,
        project_user_status_active,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    )


@pytest.fixture
def project_with_manager_user(
    user: User,
    project: Project,
    manager_role: ProjectUserRoleChoice,
    project_user_status_active: ProjectUserStatusChoice,
    storage_resource_type: ResourceType,
    allocation_status_active: AllocationStatusChoice,
    cost_attribute_type: ResourceAttributeType,
    quota_attribute_type: AllocationAttributeType,
    db,
) -> Project:
    """Create a project with a user having Manager role and Storage allocation."""
    return _create_project_with_role_user(
        project,
        user,
        manager_role,
        project_user_status_active,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    )


# ============================================================================
# Resource and Allocation Fixtures
# ============================================================================


@pytest.fixture
def cost_center(db):
    """Create a test CostCenter."""
    from coldfront_billing.models import CostCenter

    return CostCenter.objects.create(name='TEST_DEPT', cost_center_type='department')


@pytest.fixture
def cost_center_assignment(project, db):
    """Create a test CostCenterAssignment."""
    from coldfront_billing.models import CostCenter, CostCenterAssignment

    CostCenter.objects.create(name='ASSIGN_DEPT', cost_center_type='department')
    return CostCenterAssignment.objects.create(
        project=project, assignments=[{'department': 'ASSIGN_DEPT', 'percentage': 100}]
    )


@pytest.fixture
def storage_resource_type(db) -> ResourceType:
    """Create a Storage ResourceType."""
    return ResourceType.objects.get_or_create(name='Storage')[0]


@pytest.fixture
def allocation_status_active(db) -> AllocationStatusChoice:
    """Create an Active allocation status."""
    return AllocationStatusChoice.objects.get_or_create(name=AllocationStatus.ACTIVE)[0]


@pytest.fixture
def cost_attribute_type(db) -> ResourceAttributeType:
    """Create a cost attribute type for resources."""
    # First create the base AttributeType
    text_attr_type, _ = ResourceAttributeTypeBase.objects.get_or_create(name='Text')

    # Then create the ResourceAttributeType with the attribute_type
    return ResourceAttributeType.objects.get_or_create(
        name=COST_ATTR_NAME, defaults={'attribute_type': text_attr_type}
    )[0]


@pytest.fixture
def quota_attribute_type(db) -> AllocationAttributeType:
    """Create a quota attribute type for allocations."""
    # First create the base AttributeType
    float_attr_type, _ = AllocationAttributeTypeBase.objects.get_or_create(name='Float')

    # Then create the AllocationAttributeType with the attribute_type
    return AllocationAttributeType.objects.get_or_create(
        name=QUOTA_ATTR_NAME,
        defaults={
            'attribute_type': float_attr_type,
            'has_usage': True,
            'is_changeable': True,
        },
    )[0]


@pytest.fixture
def no_cost_quota_type_attribute_type(db) -> ResourceAttributeType:
    """Create a no_cost_quota_type attribute type for resources."""
    text_attr_type, _ = ResourceAttributeTypeBase.objects.get_or_create(name='Text')
    return ResourceAttributeType.objects.get_or_create(
        name=NO_COST_QUOTA_TYPE_ATTR_NAME,
        defaults={'attribute_type': text_attr_type},
    )[0]


@pytest.fixture
def no_cost_quota(user, db):
    """Create a NoCostQuota for a user."""
    from coldfront_billing.models import NoCostQuota

    return NoCostQuota.objects.create(
        user=user,
        quota_type='tier_1',
        description='Tier 1 storage',
        amount=100.0,
        units='TB',
        minimum_increment=1.0,  # Use 1.0 to avoid float modulo issues in tests
    )


# ============================================================================
# Storage Allocation Helpers & Fixtures
# ============================================================================


def add_storage_allocation_to_project(
    project: Project,
    storage_resource_type: ResourceType,
    allocation_status_active: AllocationStatusChoice,
    cost_attribute_type: ResourceAttributeType,
    quota_attribute_type: AllocationAttributeType,
    cost_value: str = '100',
    quota_value: str = '5',
    resource_name: str = 'Test Storage',
    storage_resource: Optional[Resource] = None,
    with_quota: bool = True,
):
    """Add a storage allocation to a project. Returns (allocation, storage_resource)."""
    if storage_resource is None:
        storage_resource = Resource.objects.create(
            name=resource_name,
            resource_type=storage_resource_type,
            requires_payment=True,
        )
        ResourceAttribute.objects.create(
            resource=storage_resource,
            resource_attribute_type=cost_attribute_type,
            value=cost_value,
        )
    allocation = Allocation.objects.create(
        project=project,
        status=allocation_status_active,
        quantity=100,
        justification='Test justification',
    )
    allocation.resources.add(storage_resource)
    if with_quota:
        AllocationAttribute.objects.create(
            allocation=allocation,
            allocation_attribute_type=quota_attribute_type,
            value=quota_value,
        )
    return allocation, storage_resource


def add_no_cost_quota_storage_allocation(
    project: Project,
    storage_resource_type: ResourceType,
    allocation_status_active: AllocationStatusChoice,
    cost_attribute_type: ResourceAttributeType,
    quota_attribute_type: AllocationAttributeType,
    no_cost_quota_type_attribute_type: ResourceAttributeType,
    quota_type_value: str = 'tier_1',
    resource_name: str = 'No-Cost Storage',
    quota_value: str = '5',
) -> tuple:
    """Add a storage allocation with no_cost_quota_type attribute. Returns (allocation, storage_resource)."""
    storage_resource = Resource.objects.create(
        name=resource_name,
        resource_type=storage_resource_type,
        requires_payment=True,
    )
    ResourceAttribute.objects.create(
        resource=storage_resource,
        resource_attribute_type=cost_attribute_type,
        value='100',
    )
    ResourceAttribute.objects.create(
        resource=storage_resource,
        resource_attribute_type=no_cost_quota_type_attribute_type,
        value=quota_type_value,
    )
    return add_storage_allocation_to_project(
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        storage_resource=storage_resource,
        resource_name=resource_name,
        quota_value=quota_value,
    )


@pytest.fixture
def multiple_projects(
    pi_user: User,
    project_status_active: ProjectStatusChoice,
    field_of_science: FieldOfScience,
    storage_resource_type: ResourceType,
    allocation_status_active: AllocationStatusChoice,
    cost_attribute_type: ResourceAttributeType,
    quota_attribute_type: AllocationAttributeType,
    db,
) -> List[Project]:
    """Create multiple test projects with Storage allocations."""
    projects = []
    for i in range(5):
        project = Project.objects.create(
            title=f'Test Project {i + 1}',
            pi=pi_user,
            status=project_status_active,
            field_of_science=field_of_science,
        )

        # Create a storage resource for each project
        storage_resource = Resource.objects.create(
            name=f'Storage Resource {i + 1}',
            resource_type=storage_resource_type,
            requires_payment=True,
        )

        # Add cost attribute
        ResourceAttribute.objects.create(
            resource=storage_resource,
            resource_attribute_type=cost_attribute_type,
            value=str(100 + i * 10),  # Varying costs
        )

        # Create allocation
        allocation = Allocation.objects.create(
            project=project,
            status=allocation_status_active,
            quantity=100,
            justification='Test justification',
        )
        allocation.resources.add(storage_resource)

        # Add quota attribute
        AllocationAttribute.objects.create(
            allocation=allocation,
            allocation_attribute_type=quota_attribute_type,
            value=str(5 + i),  # Varying quotas
        )

        projects.append(project)
    return projects


def create_pi_user(username_suffix: str = '') -> User:
    """Helper function to create a PI user."""
    username = f'pi{username_suffix}' if username_suffix else 'pi'
    email = f'{username}@example.com'
    return User.objects.create_user(username=username, email=email, password='pass')


def create_project_with_role_user(
    user: User,
    pi_user: User,
    project_status: ProjectStatusChoice,
    role: ProjectUserRoleChoice,
    project_user_status: ProjectUserStatusChoice,
    title: str = 'Test Project',
    with_allocation: bool = False,
    storage_resource_type: Optional[ResourceType] = None,
    allocation_status_active: Optional[AllocationStatusChoice] = None,
    cost_attribute_type: Optional[ResourceAttributeType] = None,
    quota_attribute_type: Optional[AllocationAttributeType] = None,
    field_of_science: Optional[FieldOfScience] = None,
) -> Project:
    """Helper function to create a project with a user having the given role (Billing or Manager)."""
    # Get or create field_of_science if not provided
    if field_of_science is None:
        field_of_science = FieldOfScience.objects.get_or_create(
            description='Test Field of Science', defaults={'is_selectable': True}
        )[0]

    project = Project.objects.create(
        title=title,
        pi=pi_user,
        status=project_status,
        field_of_science=field_of_science,
    )
    ProjectUser.objects.create(
        project=project,
        user=user,
        role=role,
        status=project_user_status,
    )

    # Optionally create allocation with attributes for billing view tests
    if with_allocation and all(
        [storage_resource_type, allocation_status_active, cost_attribute_type, quota_attribute_type]
    ):
        storage_resource = Resource.objects.create(
            name=f'Storage for {title}',
            resource_type=storage_resource_type,
            requires_payment=True,
        )

        ResourceAttribute.objects.create(
            resource=storage_resource,
            resource_attribute_type=cost_attribute_type,
            value='100',  # $100 per TB
        )

        allocation = Allocation.objects.create(
            project=project,
            status=allocation_status_active,
            quantity=100,
            justification='Test justification',
        )
        allocation.resources.add(storage_resource)

        AllocationAttribute.objects.create(
            allocation=allocation,
            allocation_attribute_type=quota_attribute_type,
            value='5',  # 5 TB
        )

    return project


def create_billing_request(user: User) -> HttpRequest:
    """Helper function to create an HttpRequest with a user for context processor tests."""

    request = HttpRequest()
    request.user = user
    return request
