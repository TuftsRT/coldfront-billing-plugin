import pytest
from coldfront.core.allocation.models import (
    Allocation,
    AllocationStatusChoice,
)
from coldfront.core.project.models import (
    Project,
    ProjectStatusChoice,
    ProjectUser,
    ProjectUserRoleChoice,
    ProjectUserStatusChoice,
)
from coldfront.core.resource.models import (
    Resource,
    ResourceType,
)
from django.contrib.auth.models import User


@pytest.fixture
def user(db):
    """Create a regular user."""
    return User.objects.create_user(username='testuser', email='test@example.com', password='testpass123')


@pytest.fixture
def superuser(db):
    """Create a superuser."""
    return User.objects.create_superuser(username='admin', email='admin@example.com', password='adminpass123')


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
def billing_role(db):
    """Create the Billing role."""
    return ProjectUserRoleChoice.objects.get_or_create(name='Billing')[0]


@pytest.fixture
def project_user_status_active(db):
    """Create an Active project user status."""
    return ProjectUserStatusChoice.objects.get_or_create(name='Active')[0]


@pytest.fixture
def project_user_status_inactive(db):
    """Create an Inactive project user status."""
    return ProjectUserStatusChoice.objects.get_or_create(name='Inactive')[0]


@pytest.fixture
def pi_user(db):
    """Create a PI user."""
    return User.objects.create_user(username='pi_user', email='pi@example.com', password='pipass123')


@pytest.fixture
def project(pi_user, project_status_active, db):
    """Create a test project."""
    return Project.objects.create(
        title='Test Project',
        pi=pi_user,
        status=project_status_active,
    )


@pytest.fixture
def project_with_billing_user(user, project, billing_role, project_user_status_active, db):
    """Create a project with a user having Billing role."""
    ProjectUser.objects.create(
        project=project,
        user=user,
        role=billing_role,
        status=project_user_status_active,
    )
    return project


@pytest.fixture
def storage_resource_type(db):
    """Create a Storage ResourceType."""
    return ResourceType.objects.get_or_create(name='Storage')[0]


@pytest.fixture
def storage_resource(storage_resource_type, db):
    """Create a storage resource that requires payment."""
    return Resource.objects.create(
        name='Test Storage Resource',
        resource_type=storage_resource_type,
        requires_payment=True,
    )


@pytest.fixture
def storage_resource_no_payment(storage_resource_type, db):
    """Create a storage resource that does not require payment."""
    return Resource.objects.create(
        name='Free Storage Resource',
        resource_type=storage_resource_type,
        requires_payment=False,
    )


@pytest.fixture
def allocation_status_active(db):
    """Create an Active allocation status."""
    return AllocationStatusChoice.objects.get_or_create(name='Active')[0]


@pytest.fixture
def allocation(project, storage_resource, allocation_status_active, db):
    """Create an allocation with a storage resource."""
    allocation = Allocation.objects.create(
        project=project,
        status=allocation_status_active,
        quantity=100,
    )
    allocation.resources.add(storage_resource)
    return allocation


@pytest.fixture
def multiple_projects(pi_user, project_status_active, db):
    """Create multiple test projects."""
    projects = []
    for i in range(5):
        project = Project.objects.create(
            title=f'Test Project {i+1}',
            pi=pi_user,
            status=project_status_active,
        )
        projects.append(project)
    return projects


def create_pi_user(username_suffix=''):
    """Helper function to create a PI user."""
    username = f'pi{username_suffix}' if username_suffix else 'pi'
    email = f'{username}@example.com'
    return User.objects.create_user(username=username, email=email, password='pass')


def create_project_with_billing_user(
    user, pi_user, project_status, billing_role, project_user_status, title='Test Project'
):
    """Helper function to create a project with a user having Billing role."""
    project = Project.objects.create(
        title=title,
        pi=pi_user,
        status=project_status,
    )
    ProjectUser.objects.create(
        project=project,
        user=user,
        role=billing_role,
        status=project_user_status,
    )
    return project


def create_billing_request(user):
    """Helper function to create an HttpRequest with a user for context processor tests."""
    from django.http import HttpRequest

    request = HttpRequest()
    request.user = user
    return request
