import pytest
from django.test import override_settings
from django.urls import reverse

from .conftest import add_storage_allocation_to_project, create_pi_user, create_project_with_billing_user


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
        add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
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

    def test_ordering_success(self, client, superuser):
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

    def test_context_includes_filter_parameters_for_pagination(
        self,
        client,
        superuser,
        multiple_projects,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """Test that context includes filter_parameters, all_params, and return_params."""
        response = self._get_billing_response(client, superuser, '?username=test&order_by=title&direction=asc&page=1')
        assert response.status_code == 200
        assert 'filter_parameters' in response.context
        assert 'all_params' in response.context
        assert 'return_params' in response.context
        # filter_parameters excludes order_by/direction for search form preservation
        assert 'order_by' not in response.context['filter_parameters']
        # all_params keeps them for pagination links (excludes page)
        assert 'order_by=title' in response.context['all_params']
        assert 'direction=asc' in response.context['all_params']
        assert 'page' not in response.context['all_params']
        # return_params includes full query string for back-to-billing
        assert 'order_by=title' in response.context['return_params']
        assert 'direction=asc' in response.context['return_params']
        assert 'page=1' in response.context['return_params']

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
        add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            cost_value='100',  # $100 per TB
            quota_value='5',  # 5 TB
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
        create_project_with_billing_user(
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
        create_project_with_billing_user(
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
        field_of_science,
    ):
        from django.contrib.auth.models import User

        pi_user = create_pi_user('_pi')
        billing_user1 = User.objects.create_user(
            username='searchable_billing', email='billing1@example.com', password='pass'
        )
        billing_user2 = User.objects.create_user(
            username='other_billing', email='billing2@example.com', password='pass'
        )
        create_project_with_billing_user(
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
        create_project_with_billing_user(
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
        field_of_science,
    ):
        pi_user = create_pi_user('_CamelCase')
        user = create_pi_user('_billing')
        create_project_with_billing_user(
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
        field_of_science,
    ):
        from django.contrib.auth.models import User

        pi_user = create_pi_user('_pi')
        billing_user = User.objects.create_user(
            username='searchable_user', email='billing@example.com', password='pass'
        )
        create_project_with_billing_user(
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
        create_project_with_billing_user(
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
        field_of_science,
    ):
        """Test search using both username and last_name filters."""
        from django.contrib.auth.models import User

        pi_user = User.objects.create_user(
            username='specific_username',
            email='pi@example.com',
            password='pass',
            first_name='John',
            last_name='Specific',
        )
        billing_user = create_pi_user('_billing')
        create_project_with_billing_user(
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

    def test_no_cost_center_filter_includes_only_projects_without_assignment(
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
        """Test that no_cost_center filter returns only projects without cost center assignments."""
        from coldfront_billing.models import CostCenter, CostCenterAssignment

        pi_user = create_pi_user('_pi')
        billing_user = create_pi_user('_billing')

        project_with_assignment = create_project_with_billing_user(
            billing_user,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Project With Cost Center',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )
        CostCenter.objects.create(dept_id='DEPT001')
        CostCenterAssignment.objects.create(
            project=project_with_assignment,
            assignments={'DEPT001': 100},
        )

        create_project_with_billing_user(
            billing_user,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Project Without Cost Center',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
            field_of_science=field_of_science,
        )

        # Without filter: both projects visible
        response = self._get_billing_response(client, superuser)
        assert response.status_code == 200
        project_titles = [p.title for p in response.context['project_list']]
        assert 'Project With Cost Center' in project_titles
        assert 'Project Without Cost Center' in project_titles

        # With no_cost_center=on: only project without assignment
        response = self._get_billing_response(client, superuser, '?no_cost_center=on')
        assert response.status_code == 200
        project_titles = [p.title for p in response.context['project_list']]
        assert 'Project With Cost Center' not in project_titles
        assert 'Project Without Cost Center' in project_titles


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
    ):
        """Test ordering by PI username ascending."""
        # Create projects with different PI usernames
        pi_users = [
            create_pi_user('_zebra'),  # Should be last
            create_pi_user('_alpha'),  # Should be first
            create_pi_user('_beta'),  # Should be middle
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


@pytest.mark.django_db
class TestBillingDetailsView:
    """Test suite for BillingDetailsView."""

    @staticmethod
    def _get_billing_details_response(client, user, project_id):
        """Helper method to get billing details view response."""
        client.force_login(user)
        url = reverse('billing_details', kwargs={'project_id': project_id})
        return client.get(url)

    def test_unauthenticated_user_redirected(self, client, project):
        """Test that unauthenticated users are redirected to login."""
        url = reverse('billing_details', kwargs={'project_id': project.id})
        response = client.get(url)
        assert response.status_code == 302
        assert '/login' in response.url

    def test_superuser_can_view_project_details(
        self,
        client,
        superuser,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """Test that superusers can view billing details for any project."""
        allocation, _ = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
        )

        response = self._get_billing_details_response(client, superuser, project.id)

        assert response.status_code == 200
        assert response.context['project'] == project
        assert len(response.context['allocations']) == 1
        assert response.context['total_cost'] == 500

        billing_alloc = response.context['allocations'][0]
        assert billing_alloc.allocation_id == allocation.id
        assert billing_alloc.total_cost == 500
        assert billing_alloc.extra['project_title'] == project.title
        assert billing_alloc.extra['pi_name'] == project.pi.username
        assert billing_alloc.extra['resource_name'] == 'Test Storage'
        assert billing_alloc.extra['status'] == 'Active'

    def test_user_with_billing_role_can_view_project_details(
        self,
        client,
        user,
        project_with_billing_user,
    ):
        """Test that users with Billing role can view their project's billing details."""
        response = self._get_billing_details_response(client, user, project_with_billing_user.id)

        assert response.status_code == 200
        assert response.context['project'] == project_with_billing_user
        assert len(response.context['allocations']) == 1
        assert response.context['total_cost'] == 500

    def test_pi_can_view_own_project_details(
        self,
        client,
        pi_user,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """Test that PI can view billing details for their own project."""
        add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            resource_name='PI Storage',
            cost_value='50',
            quota_value='4',
        )

        response = self._get_billing_details_response(client, pi_user, project.id)

        assert response.status_code == 200
        assert response.context['project'] == project
        assert len(response.context['allocations']) == 1
        # 4 TB * $50 = $200
        assert response.context['total_cost'] == 200

    def test_user_without_permission_redirected_with_error(
        self,
        client,
        user,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """Test that users without Billing role or PI access are redirected with error."""
        add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
        )
        response = self._get_billing_details_response(client, user, project.id)

        assert response.status_code == 302
        assert response.url == reverse('billing_index')

    def test_nonexistent_project_returns_404(self, client, superuser):
        """Test that requesting nonexistent project returns 404."""
        response = self._get_billing_details_response(client, superuser, 99999)
        assert response.status_code == 404

    def test_empty_allocations_when_project_has_no_storage(
        self,
        client,
        superuser,
        project,
    ):
        """Test that project with no Storage allocations shows empty list."""
        response = self._get_billing_details_response(client, superuser, project.id)

        assert response.status_code == 200
        assert response.context['allocations'] == []
        assert response.context['total_cost'] == 0

    def test_allocations_sorted_by_allocation_id(
        self,
        client,
        superuser,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """Test that allocations in context are sorted by allocation_id."""
        allocation1, storage_resource = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            quota_value='5',
        )
        add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            storage_resource=storage_resource,
            quota_value='3',
        )

        response = self._get_billing_details_response(client, superuser, project.id)

        assert response.status_code == 200
        allocations = response.context['allocations']
        assert len(allocations) == 2
        assert allocations[0].allocation_id <= allocations[1].allocation_id

    def test_context_includes_project_and_total_cost(
        self,
        client,
        superuser,
        project_with_billing_user,
    ):
        """Test that context includes project and total_cost."""
        response = self._get_billing_details_response(client, superuser, project_with_billing_user.id)

        assert response.status_code == 200
        assert 'project' in response.context
        assert 'allocations' in response.context
        assert 'total_cost' in response.context
        assert isinstance(response.context['total_cost'], int)

    def test_details_view_passes_return_params_for_back_button(
        self,
        client,
        superuser,
        project_with_billing_user,
    ):
        """Test that billing details view passes return_params for Back to Billing link."""
        client.force_login(superuser)
        url = reverse('billing_details', kwargs={'project_id': project_with_billing_user.id})
        response = client.get(url + '?username=foo&order_by=title&direction=asc&page=2')

        assert response.status_code == 200
        assert 'return_params' in response.context
        assert 'username=foo' in response.context['return_params']
        assert 'order_by=title' in response.context['return_params']
        assert 'page=2' in response.context['return_params']


@pytest.mark.django_db
class TestCostCenterAssignmentUpdateView:
    """Test suite for CostCenterAssignmentUpdateView."""

    @staticmethod
    def _post_cost_center_assignment(client, user, project_id, assignments_data):
        """Helper method to post cost center assignment update."""
        import json

        client.force_login(user)
        url = reverse('update_cost_center_assignment')
        data = {'project_id': project_id, 'assignments': json.dumps(assignments_data)}
        return client.post(url, data=data)

    def test_unauthenticated_user_redirected(self, client, project):
        """Test that unauthenticated users are redirected to login."""
        url = reverse('update_cost_center_assignment')
        response = client.post(url, data={})
        assert response.status_code == 302
        assert '/login' in response.url

    def test_superuser_can_update_any_project(self, client, superuser, project):
        """Test that superusers can update cost center assignments for any project."""
        from coldfront_billing.models import CostCenter

        CostCenter.objects.create(dept_id='DEPT001')

        assignments_data = {'DEPT001': 100}

        response = self._post_cost_center_assignment(client, superuser, project.id, assignments_data)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data['success'] is True
        assert 'Cost center assignment updated successfully' in response_data['message']
        assert response_data['assignments'] == assignments_data

    def test_regular_user_without_billing_role_forbidden(self, client, user, project):
        """Test that users without Billing role cannot update cost center assignments."""
        from coldfront_billing.models import CostCenter

        CostCenter.objects.create(dept_id='DEPT003')

        assignments_data = {'DEPT003': 75}

        response = self._post_cost_center_assignment(client, user, project.id, assignments_data)

        assert response.status_code == 403
        response_data = response.json()
        assert response_data['success'] is False
        assert 'You do not have permission' in response_data['error']

    def test_update_existing_cost_center_assignment_success(self, client, superuser, project):
        """Test updating an existing cost center assignment."""
        from coldfront_billing.models import CostCenter, CostCenterAssignment

        CostCenter.objects.create(dept_id='DEPT004')
        CostCenter.objects.create(dept_id='DEPT005')

        # Create initial assignment
        initial_assignments = {'DEPT004': 100}
        CostCenterAssignment.objects.create(project=project, assignments=initial_assignments)

        # Update with new assignments
        new_assignments = {'DEPT004': 60, 'DEPT005': 40}

        response = self._post_cost_center_assignment(client, superuser, project.id, new_assignments)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data['success'] is True
        assert response_data['assignments'] == new_assignments

        # Verify in database
        assignment = CostCenterAssignment.objects.get(project=project)
        assert assignment.assignments == new_assignments

    def test_invalid_json_format_returns_error(self, client, superuser, project):
        """Test that invalid JSON format returns validation error."""
        client.force_login(superuser)
        url = reverse('update_cost_center_assignment')

        # Send invalid JSON
        data = {'project_id': project.id, 'assignments': 'invalid-json-string'}

        response = client.post(url, data=data)

        assert response.status_code == 400
        response_data = response.json()
        assert response_data['success'] is False
        assert 'errors' in response_data

    def test_nonexistent_cost_center_returns_error(self, client, superuser, project):
        """Test that referencing nonexistent cost center returns validation error."""
        # Don't create the cost center - it should not exist
        assignments_data = {'NONEXISTENT': 100}

        response = self._post_cost_center_assignment(client, superuser, project.id, assignments_data)

        assert response.status_code == 400
        response_data = response.json()
        assert response_data['success'] is False
        assert 'errors' in response_data

    def test_missing_project_id_field_returns_error(self, client, superuser, project):
        """Test that missing project_id field returns validation error."""
        import json

        from coldfront_billing.models import CostCenter

        CostCenter.objects.create(dept_id='DEPT008')
        client.force_login(superuser)
        url = reverse('update_cost_center_assignment')

        # Missing project_id field
        data = {'assignments': json.dumps({'DEPT008': 100})}

        response = client.post(url, data=data)

        assert response.status_code == 400
        response_data = response.json()
        assert response_data['success'] is False
        assert 'errors' in response_data

    def test_missing_assignments_field_returns_error(self, client, superuser, project):
        """Test that missing assignments field returns validation error."""
        client.force_login(superuser)
        url = reverse('update_cost_center_assignment')

        # Missing assignments field
        data = {'project_id': project.id}

        response = client.post(url, data=data)

        assert response.status_code == 400
        response_data = response.json()
        assert response_data['success'] is False
        assert 'errors' in response_data

    def test_multiple_cost_centers_assignment(self, client, superuser, project):
        """Test assigning multiple cost centers with different percentages."""
        from coldfront_billing.models import CostCenter

        for dept_id in ('DEPT009', 'DEPT010', 'DEPT011'):
            CostCenter.objects.create(dept_id=dept_id)

        assignments_data = {'DEPT009': 50, 'DEPT010': 30, 'DEPT011': 20}

        response = self._post_cost_center_assignment(client, superuser, project.id, assignments_data)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data['success'] is True
        assert response_data['assignments'] == assignments_data

    def test_inactive_billing_user_forbidden(self, client, user, project, billing_role, project_user_status_inactive):
        """Test that users with Inactive Billing role cannot update cost center assignments."""
        from coldfront.core.project.models import ProjectUser

        from coldfront_billing.models import CostCenter

        # Create inactive billing user relationship
        ProjectUser.objects.create(
            project=project,
            user=user,
            role=billing_role,
            status=project_user_status_inactive,  # Inactive status
        )

        CostCenter.objects.create(dept_id='DEPT013')
        assignments_data = {'DEPT013': 100}

        response = self._post_cost_center_assignment(client, user, project.id, assignments_data)

        assert response.status_code == 403
        response_data = response.json()
        assert response_data['success'] is False
        assert 'You do not have permission' in response_data['error']

    def test_assignments_non_dict_format_returns_error(self, client, superuser, project):
        """Test that assignments in non-dictionary format returns validation error."""
        import json

        client.force_login(superuser)
        url = reverse('update_cost_center_assignment')

        # Send assignments as a list instead of dictionary
        data = {'project_id': project.id, 'assignments': json.dumps([{'dept_id': 'DEPT014', 'percentage': 100}])}

        response = client.post(url, data=data)

        assert response.status_code == 400
        response_data = response.json()
        assert response_data['success'] is False
        assert 'errors' in response_data

    def test_get_request_not_allowed(self, client, superuser, project):
        """Test that GET requests are not allowed (only POST)."""
        client.force_login(superuser)
        url = reverse('update_cost_center_assignment')

        response = client.get(url)

        # Should return 405 Method Not Allowed since view only accepts POST
        assert response.status_code == 405

    def test_cost_center_assignment_created_if_not_exists(self, client, superuser, project):
        """Test that CostCenterAssignment is created if it doesn't exist."""
        from coldfront_billing.models import CostCenter, CostCenterAssignment

        # Ensure no assignment exists initially
        assert not CostCenterAssignment.objects.filter(project=project).exists()

        CostCenter.objects.create(dept_id='DEPT015')
        assignments_data = {'DEPT015': 100}

        response = self._post_cost_center_assignment(client, superuser, project.id, assignments_data)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data['success'] is True

        # Verify assignment was created
        assert CostCenterAssignment.objects.filter(project=project).exists()
        assignment = CostCenterAssignment.objects.get(project=project)
        assert assignment.assignments == assignments_data
