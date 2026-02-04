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

from coldfront_billing.constants import COST_ATTR_NAME, QUOTA_ATTR_NAME

# ============================================================================
# User Fixtures
# ============================================================================


@pytest.fixture
def user(db):
    """Create a regular user."""
    return User.objects.create_user(username='testuser', email='test@example.com', password='testpass123')


@pytest.fixture
def superuser(db):
    """Create a superuser."""
    return User.objects.create_superuser(username='admin', email='admin@example.com', password='adminpass123')


@pytest.fixture
def pi_user(db):
    """Create a PI user."""
    return User.objects.create_user(username='pi_user', email='pi@example.com', password='pipass123')


# ============================================================================
# Project Status and Role Fixtures
# ============================================================================


@pytest.fixture
def project_status_active(db):
    """Create an Active project status."""
    return ProjectStatusChoice.objects.get_or_create(name='Active')[0]


@pytest.fixture
def project_status_archived(db):
    """Create an Archived project status."""
    return ProjectStatusChoice.objects.get_or_create(name='Archived')[0]


@pytest.fixture
def project_status_new(db):
    """Create a New project status."""
    return ProjectStatusChoice.objects.get_or_create(name='New')[0]


@pytest.fixture
def billing_role_choice(db):
    """Create the Billing role."""
    return ProjectUserRoleChoice.objects.get_or_create(name='Billing')[0]


@pytest.fixture
def billing_role(billing_role_choice):
    """Alias for billing_role_choice for backward compatibility."""
    return billing_role_choice


@pytest.fixture
def project_user_status_active(db):
    """Create an Active project user status."""
    return ProjectUserStatusChoice.objects.get_or_create(name='Active')[0]


@pytest.fixture
def project_user_status_inactive(db):
    """Create an Inactive project user status."""
    return ProjectUserStatusChoice.objects.get_or_create(name='Inactive')[0]


# ============================================================================
# Project Fixtures
# ============================================================================


@pytest.fixture
def field_of_science(db):
    """Create a FieldOfScience for projects."""
    return FieldOfScience.objects.get_or_create(description='Test Field of Science', defaults={'is_selectable': True})[
        0
    ]


@pytest.fixture
def project(pi_user, project_status_active, field_of_science, db):
    """Create a test project."""
    return Project.objects.create(
        title='Test Project',
        pi=pi_user,
        status=project_status_active,
        field_of_science=field_of_science,
    )


@pytest.fixture
def project_with_billing_user(
    user,
    project,
    billing_role,
    project_user_status_active,
    storage_resource_type,
    allocation_status_active,
    cost_attribute_type,
    quota_attribute_type,
    db,
):
    """Create a project with a user having Billing role and Storage allocation."""
    ProjectUser.objects.create(
        project=project,
        user=user,
        role=billing_role,
        status=project_user_status_active,
    )

    # Add Storage allocation for billing view
    storage_resource = Resource.objects.create(
        name='Test Storage',
        resource_type=storage_resource_type,
        requires_payment=True,
    )
    ResourceAttribute.objects.create(
        resource=storage_resource,
        resource_attribute_type=cost_attribute_type,
        value='100',
    )
    allocation = Allocation.objects.create(
        project=project,
        status=allocation_status_active,
        quantity=100,
    )
    allocation.resources.add(storage_resource)
    AllocationAttribute.objects.create(
        allocation=allocation,
        allocation_attribute_type=quota_attribute_type,
        value='5',
    )

    return project


# ============================================================================
# Resource and Allocation Fixtures
# ============================================================================


@pytest.fixture
def storage_resource_type(db):
    """Create a Storage ResourceType."""
    return ResourceType.objects.get_or_create(name='Storage')[0]


@pytest.fixture
def allocation_status_active(db):
    """Create an Active allocation status."""
    return AllocationStatusChoice.objects.get_or_create(name='Active')[0]


@pytest.fixture
def cost_attribute_type(db):
    """Create a cost attribute type for resources."""
    # First create the base AttributeType
    text_attr_type, _ = ResourceAttributeTypeBase.objects.get_or_create(name='Text')

    # Then create the ResourceAttributeType with the attribute_type
    return ResourceAttributeType.objects.get_or_create(
        name=COST_ATTR_NAME, defaults={'attribute_type': text_attr_type}
    )[0]


@pytest.fixture
def quota_attribute_type(db):
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


# ============================================================================
# Helper Functions
# ============================================================================


@pytest.fixture
def multiple_projects(
    pi_user,
    project_status_active,
    field_of_science,
    storage_resource_type,
    allocation_status_active,
    cost_attribute_type,
    quota_attribute_type,
    db,
):
    """Create multiple test projects with Storage allocations."""
    projects = []
    for i in range(5):
        project = Project.objects.create(
            title=f'Test Project {i+1}',
            pi=pi_user,
            status=project_status_active,
            field_of_science=field_of_science,
        )

        # Create a storage resource for each project
        storage_resource = Resource.objects.create(
            name=f'Storage Resource {i+1}',
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


def create_pi_user(username_suffix=''):
    """Helper function to create a PI user."""
    username = f'pi{username_suffix}' if username_suffix else 'pi'
    email = f'{username}@example.com'
    return User.objects.create_user(username=username, email=email, password='pass')


def create_project_with_billing_user(
    user,
    pi_user,
    project_status,
    billing_role,
    project_user_status,
    title='Test Project',
    with_allocation=False,
    storage_resource_type=None,
    allocation_status_active=None,
    cost_attribute_type=None,
    quota_attribute_type=None,
    field_of_science=None,
):
    """Helper function to create a project with a user having Billing role."""
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
        role=billing_role,
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
        )
        allocation.resources.add(storage_resource)

        AllocationAttribute.objects.create(
            allocation=allocation,
            allocation_attribute_type=quota_attribute_type,
            value='5',  # 5 TB
        )

    return project


def create_billing_request(user):
    """Helper function to create an HttpRequest with a user for context processor tests."""
    from django.http import HttpRequest

    request = HttpRequest()
    request.user = user
    return request
