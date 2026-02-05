import pytest
from coldfront.core.allocation.models import Allocation, AllocationAttribute
from coldfront.core.resource.models import Resource, ResourceAttribute
from django.test import override_settings
from django.urls import reverse

from .conftest import create_pi_user, create_project_with_billing_user


@pytest.fixture(autouse=True)
def configure_urls():
    """Configure URLs for view tests."""
    with override_settings(ROOT_URLCONF='coldfront_billing.tests.conftest_urls'):
        yield


@pytest.mark.django_db
class TestBillingView:
    """Test suite for BillingView."""

    @staticmethod
    def _get_billing_response(client, user, query_params=''):
        """Helper method to get billing view response."""
        client.force_login(user)
        url = reverse('billing_index') + query_params
        return client.get(url)

    def test_unauthenticated_user_redirected(self, client):
        """Test that unauthenticated users are redirected to login."""
        url = reverse('billing_index')
        response = client.get(url)
        assert response.status_code == 302
        assert '/login' in response.url

    def test_superuser_sees_all_projects(
        self,
        client,
        superuser,
        multiple_projects,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """Test that superusers can see all projects with Storage allocations."""
        response = self._get_billing_response(client, superuser)
        assert response.status_code == 200
        # All 5 projects should have Storage allocations
        assert len(response.context['project_list']) == 5

    def test_regular_user_without_billing_role_sees_nothing(
        self,
        client,
        user,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """Test that regular users without Billing role see no projects."""
        # Even if project has allocation, user without billing role shouldn't see it
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

        response = self._get_billing_response(client, user)
        assert response.status_code == 200
        assert len(response.context['project_list']) == 0

    def test_regular_user_with_billing_role_sees_projects(self, client, user, project_with_billing_user):
        """Test that users with Billing role can see their projects with Storage allocations."""
        # project_with_billing_user fixture already includes Storage allocation
        response = self._get_billing_response(client, user)
        assert response.status_code == 200
        assert len(response.context['project_list']) == 1
        assert response.context['project_list'][0] == project_with_billing_user

    def test_user_only_sees_active_project_user_status(
        self,
        client,
        user,
        project_status_active,
        billing_role,
        project_user_status_active,
        project_user_status_inactive,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        db,
    ):
        """Test that only Active ProjectUser status is shown."""
        pi_user1 = create_pi_user('1')
        active_project = create_project_with_billing_user(
            user,
            pi_user1,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Active User Project',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
        )

        pi_user2 = create_pi_user('2')
        inactive_project = create_project_with_billing_user(
            user,
            pi_user2,
            project_status_active,
            billing_role,
            project_user_status_inactive,
            'Inactive User Project',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
        )

        response = self._get_billing_response(client, user)
        assert response.status_code == 200
        project_ids = [p.id for p in response.context['project_list']]
        assert active_project.id in project_ids
        assert inactive_project.id not in project_ids

    def test_ordering_success(
        self,
        client,
        superuser
    ):
        # Test ascending order
        response = self._get_billing_response(client, superuser, '?order_by=id&direction=asc')
        assert response.status_code == 200
        ids = [p.id for p in response.context['project_list']]
        assert ids == sorted(ids)

        # Test descending order
        response = self._get_billing_response(client, superuser, '?order_by=id&direction=des')
        assert response.status_code == 200
        ids = [p.id for p in response.context['project_list']]
        assert ids == sorted(ids, reverse=True)

    def test_context_includes_cost_and_cost_centers(
        self,
        client,
        superuser,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """Test that each project in context has cost and cost_centers."""
        # Create Storage allocation with attributes
        storage_resource = Resource.objects.create(
            name='Test Storage',
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

        response = self._get_billing_response(client, superuser)
        assert response.status_code == 200
        assert len(response.context['project_list']) == 1

        for project_obj in response.context['project_list']:
            assert hasattr(project_obj, 'cost')
            assert project_obj.cost.startswith('$')
            # Cost = quota (5 TB) * cost_per_tb (100) = 500
            cost_value = int(project_obj.cost.replace('$', ''))
            assert cost_value == 500
            assert hasattr(project_obj, 'cost_centers')
            assert project_obj.cost_centers == '-'


@pytest.mark.django_db
class TestBillingViewSearchFilters:

    @staticmethod
    def _get_billing_response(client, user, query_params=''):
        client.force_login(user)
        url = reverse('billing_index') + query_params
        return client.get(url)

    def test_search_by_pi_user_success(
        self,
        client,
        superuser,
        project_status_active,
        billing_role,
        project_user_status_active,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        field_of_science,
    ):
        pi_user1 = create_pi_user('_searchable')
        pi_user2 = create_pi_user('_other')
        user = create_pi_user('_billing')
        project1 = create_project_with_billing_user(
            user,
            pi_user1,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Project 1',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )
        project2 = create_project_with_billing_user(
            user,
            pi_user2,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Project 2',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )

        response = self._get_billing_response(client, superuser, '?username=searchable')

        assert response.status_code == 200
        project_titles = [p.title for p in response.context['project_list']]
        assert 'Project 1' in project_titles
        assert 'Project 2' not in project_titles

    def test_search_by_project_user_success(
        self,
        client,
        superuser,
        project_status_active,
        billing_role,
        project_user_status_active,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        field_of_science
    ):
        from django.contrib.auth.models import User
        from coldfront.core.project.models import ProjectUser

        pi_user = create_pi_user('_pi')
        billing_user1 = User.objects.create_user(username='searchable_billing', email='billing1@example.com', password='pass')
        billing_user2 = User.objects.create_user(username='other_billing', email='billing2@example.com', password='pass')
        project1 = create_project_with_billing_user(
            billing_user1,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Project with searchable user',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )
        project2 = create_project_with_billing_user(
            billing_user2,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Project with other user',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )

        response = self._get_billing_response(client, superuser, '?username=searchable')
        assert response.status_code == 200
        project_titles = [p.title for p in response.context['project_list']]
        assert 'Project with searchable user' in project_titles
        assert 'Project with other user' not in project_titles

    def test_search_case_insensitive(
        self,
        client,
        superuser,
        project_status_active,
        billing_role,
        project_user_status_active,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        field_of_science
    ):
        pi_user = create_pi_user('_CamelCase')
        user = create_pi_user('_billing')
        project = create_project_with_billing_user(
            user,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_active,
            'CamelCase Project',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )

        # Test lowercase search
        response = self._get_billing_response(client, superuser, '?username=camelcase')
        assert response.status_code == 200
        assert len(response.context['project_list']) == 1
        assert response.context['project_list'][0].title == 'CamelCase Project'

    def test_search_with_empty_username_returns_all_projects(
        self,
        client,
        superuser,
        multiple_projects,
    ):
        response = self._get_billing_response(client, superuser, '?username=')

        assert response.status_code == 200
        assert len(response.context['project_list']) == 5

    def test_search_by_user_name_no_matches(
        self,
        client,
        superuser,
        multiple_projects,
    ):
        response = self._get_billing_response(client, superuser, '?username=nonexistent')

        assert response.status_code == 200
        assert len(response.context['project_list']) == 0

    def test_search_form_included_in_context(
        self,
        client,
        superuser,
        multiple_projects,
    ):
        response = self._get_billing_response(client, superuser, '?username=test')

        assert response.status_code == 200
        assert 'billing_search_form' in response.context
        form = response.context['billing_search_form']
        assert form.initial.get('username') == 'test' or form.data.get('username') == 'test'

    def test_search_filters_only_active_project_users(
        self,
        client,
        superuser,
        project_status_active,
        billing_role,
        project_user_status_active,
        project_user_status_inactive,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        field_of_science
    ):
        from django.contrib.auth.models import User
        from coldfront.core.project.models import ProjectUser

        pi_user = create_pi_user('_pi')
        billing_user = User.objects.create_user(username='searchable_user', email='billing@example.com', password='pass')
        active_project = create_project_with_billing_user(
            billing_user,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Active User Project',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )
        inactive_project = create_project_with_billing_user(
            billing_user,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_inactive,
            'Inactive User Project',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )

        response = self._get_billing_response(client, superuser, '?username=searchable')

        assert response.status_code == 200
        project_titles = [p.title for p in response.context['project_list']]
        # Should only include project where user has Active status
        assert 'Active User Project' in project_titles
        assert 'Inactive User Project' not in project_titles

    def test_search_multiple_fields_combined(
        self,
        client,
        superuser,
        project_status_active,
        billing_role,
        project_user_status_active,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        field_of_science
    ):
        """Test search using both username and last_name filters."""
        from django.contrib.auth.models import User
        pi_user = User.objects.create_user(
            username='specific_username',
            email='pi@example.com',
            password='pass',
            first_name='John',
            last_name='Specific'
        )
        billing_user = create_pi_user('_billing')
        project = create_project_with_billing_user(
            billing_user,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Specific Project',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )

        response = self._get_billing_response(client, superuser, '?username=specific&last_name=Specific')

        assert response.status_code == 200
        assert len(response.context['project_list']) == 1
        assert response.context['project_list'][0].title == 'Specific Project'


@pytest.mark.django_db
class TestBillingViewOrdering:
    """Test suite for BillingView ordering functionality."""

    @staticmethod
    def _get_billing_response(client, user, query_params=''):
        """Helper method to get billing view response."""
        client.force_login(user)
        url = reverse('billing_index') + query_params
        return client.get(url)

    def test_default_ordering(
        self,
        client,
        superuser,
        multiple_projects,
    ):
        response = self._get_billing_response(client, superuser)

        assert response.status_code == 200
        project_ids = [p.id for p in response.context['project_list']]
        assert project_ids == sorted(project_ids)

    def test_ascending_ordering_success(
        self,
        client,
        superuser,
        multiple_projects,
    ):
        response = self._get_billing_response(client, superuser, '?order_by=id&direction=asc')

        assert response.status_code == 200
        project_ids = [p.id for p in response.context['project_list']]
        assert project_ids == sorted(project_ids)

    def test_descending_ordering_success(
        self,
        client,
        superuser,
        multiple_projects,
    ):
        response = self._get_billing_response(client, superuser, '?order_by=id&direction=des')

        assert response.status_code == 200
        project_ids = [p.id for p in response.context['project_list']]
        assert project_ids == sorted(project_ids, reverse=True)

    def test_ordering_by_title_ascending(
        self,
        client,
        superuser,
        multiple_projects,
    ):
        """Test ordering by title ascending."""
        response = self._get_billing_response(client, superuser, '?order_by=title&direction=asc')
        assert response.status_code == 200
        project_titles = [p.title for p in response.context['project_list']]
        assert project_titles == sorted(project_titles)

    def test_ordering_by_title_descending(
        self,
        client,
        superuser,
        multiple_projects,
    ):
        """Test ordering by title descending."""
        response = self._get_billing_response(client, superuser, '?order_by=title&direction=des')
        assert response.status_code == 200
        project_titles = [p.title for p in response.context['project_list']]
        assert project_titles == sorted(project_titles, reverse=True)

    def test_ordering_by_pi_username_ascending(
        self,
        client,
        superuser,
        project_status_active,
        billing_role,
        project_user_status_active,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        field_of_science,
        db,
    ):
        """Test ordering by PI username ascending."""
        # Create projects with different PI usernames
        pi_users = [
            create_pi_user('_zebra'),  # Should be last
            create_pi_user('_alpha'),  # Should be first
            create_pi_user('_beta'),   # Should be middle
        ]

        billing_user = create_pi_user('_billing')

        projects = []
        for i, pi_user in enumerate(pi_users):
            project = create_project_with_billing_user(
                billing_user,
                pi_user,
                project_status_active,
                billing_role,
                project_user_status_active,
                f'Project {i}',
                with_allocation=True,
                storage_resource_type=storage_resource_type,
                allocation_status_active=allocation_status_active,
                cost_attribute_type=cost_attribute_type,
                quota_attribute_type=quota_attribute_type,
                field_of_science=field_of_science,
            )
            projects.append(project)

        response = self._get_billing_response(client, superuser, '?order_by=pi__username&direction=asc')
        assert response.status_code == 200
        pi_usernames = [p.pi.username for p in response.context['project_list']]
        assert pi_usernames == sorted(pi_usernames)

    def test_ordering_by_pi_username_descending(
        self,
        client,
        superuser,
        project_status_active,
        billing_role,
        project_user_status_active,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        field_of_science,
    ):
        """Test ordering by PI username descending."""
        # Create projects with different PI usernames
        pi_users = [
            create_pi_user('_alpha'),
            create_pi_user('_beta'),
            create_pi_user('_zebra'),
        ]

        billing_user = create_pi_user('_billing')

        for i, pi_user in enumerate(pi_users):
            create_project_with_billing_user(
                billing_user,
                pi_user,
                project_status_active,
                billing_role,
                project_user_status_active,
                f'Project {i}',
                with_allocation=True,
                storage_resource_type=storage_resource_type,
                allocation_status_active=allocation_status_active,
                cost_attribute_type=cost_attribute_type,
                quota_attribute_type=quota_attribute_type,
                field_of_science=field_of_science,
            )

        response = self._get_billing_response(client, superuser, '?order_by=pi__username&direction=des')
        assert response.status_code == 200
        pi_usernames = [p.pi.username for p in response.context['project_list']]
        assert pi_usernames == sorted(pi_usernames, reverse=True)

    def test_ordering_with_invalid_direction_defaults_to_asc(
        self,
        client,
        superuser,
        multiple_projects,
    ):
        """Test that invalid direction parameter defaults to ascending."""
        response = self._get_billing_response(client, superuser, '?order_by=id&direction=invalid')
        assert response.status_code == 200
        project_ids = [p.id for p in response.context['project_list']]
        assert project_ids == sorted(project_ids)  # Should default to ascending

