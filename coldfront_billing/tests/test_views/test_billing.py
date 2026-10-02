import pytest
from django.urls import reverse

from coldfront_billing.tests.conftest import (
    add_storage_allocation_to_project,
    create_pi_user,
    create_project_with_role_user,
)
from coldfront_billing.tests.test_views.common import get_billing_response


@pytest.mark.django_db
@pytest.mark.usefixtures('configure_urls')
class TestBillingView:
    """Test suite for BillingView."""

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
        response = get_billing_response(client, superuser)
        assert response.status_code == 200
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
        add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
        )

        response = get_billing_response(client, user)
        assert response.status_code == 200
        assert len(response.context['project_list']) == 0

    def test_regular_user_with_billing_role_sees_projects(self, client, user, project_with_billing_user):
        """Test that users with Billing role can see their projects with Storage allocations."""
        response = get_billing_response(client, user)
        assert response.status_code == 200
        assert len(response.context['project_list']) == 1
        assert response.context['project_list'][0] == project_with_billing_user

    def test_regular_user_with_manager_role_sees_projects(self, client, user, project_with_manager_user):
        """Test that users with Manager role can see their projects with Storage allocations."""
        response = get_billing_response(client, user)
        assert response.status_code == 200
        assert len(response.context['project_list']) == 1
        assert response.context['project_list'][0] == project_with_manager_user

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
        active_project = create_project_with_role_user(
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
        inactive_project = create_project_with_role_user(
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

        response = get_billing_response(client, user)
        assert response.status_code == 200
        project_ids = [p.id for p in response.context['project_list']]
        assert active_project.id in project_ids
        assert inactive_project.id not in project_ids

    def test_user_with_manager_role_only_sees_active_project_user_status(
        self,
        client,
        user,
        project_status_active,
        manager_role,
        project_user_status_active,
        project_user_status_inactive,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """Test that Manager role users only see projects where their status is Active."""
        pi_user1 = create_pi_user('_mgr1')
        active_project = create_project_with_role_user(
            user,
            pi_user1,
            project_status_active,
            manager_role,
            project_user_status_active,
            'Active Manager Project',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
        )

        pi_user2 = create_pi_user('_mgr2')
        create_project_with_role_user(
            user,
            pi_user2,
            project_status_active,
            manager_role,
            project_user_status_inactive,
            'Inactive Manager Project',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
        )

        response = get_billing_response(client, user)
        assert response.status_code == 200
        project_ids = [p.id for p in response.context['project_list']]
        assert active_project.id in project_ids
        # Inactive Manager project should not appear
        assert len(project_ids) == 1

    def test_ordering_success(self, client, superuser, multiple_projects):
        response = get_billing_response(client, superuser, '?order_by=id&direction=asc')
        assert response.status_code == 200
        ids = [p.id for p in response.context['project_list']]
        assert ids == sorted(ids)

        response = get_billing_response(client, superuser, '?order_by=id&direction=des')
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
        response = get_billing_response(client, superuser, '?username=test&order_by=title&direction=asc&page=1')
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
            cost_value='100',
            quota_value='5',
        )

        response = get_billing_response(client, superuser)
        assert response.status_code == 200
        assert len(response.context['project_list']) == 1

        for project_obj in response.context['project_list']:
            assert hasattr(project_obj, 'cost')
            assert project_obj.cost.startswith('$')
            cost_value = float(project_obj.cost.replace('$', ''))
            assert cost_value == 500
            assert hasattr(project_obj, 'cost_centers')
            assert project_obj.cost_centers == ''

    def test_cost_center_popover_escapes_assignment_text(
        self,
        client,
        superuser,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """Cost center text is escaped; only the <br> separators reach the popover as markup."""
        from coldfront_billing.models import CostCenterAssignment

        add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            cost_value='100',
            quota_value='5',
        )
        CostCenterAssignment.objects.create(
            project=project,
            assignments=[
                {'department': 'A<b>', 'percentage': 60},
                {'department': 'DEPT2', 'grant': 'G1', 'percentage': 40},
            ],
        )

        response = get_billing_response(client, superuser)
        assert response.status_code == 200

        project_obj = response.context['project_list'][0]
        assert project_obj.all_cost_centers == 'A&lt;b&gt;: 60%<br>DEPT2.G1: 40%'
        # the attribute is escaped once more, since the browser unescapes it before Bootstrap renders it as HTML
        assert 'data-bs-content="A&amp;lt;b&amp;gt;: 60%&lt;br&gt;DEPT2.G1: 40%"' in response.content.decode()

    def test_sort_headers_reverse_the_current_sort(
        self,
        client,
        superuser,
        multiple_projects,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """The sorted column links to the opposite direction; the others link to ascending."""
        response = get_billing_response(client, superuser, '?order_by=title&direction=asc&project_title=Project')
        content = response.content.decode()

        titles = [p.title for p in response.context['project_list']]
        assert titles == sorted(titles)
        assert content.count('aria-sort=') == 1
        assert 'aria-sort="ascending"' in content
        assert 'href="?order_by=title&direction=des&project_title=Project"' in content
        assert 'href="?order_by=pi&direction=asc&project_title=Project"' in content

        response = get_billing_response(client, superuser, '?order_by=title&direction=des')
        content = response.content.decode()
        assert 'aria-sort="descending"' in content
        assert 'href="?order_by=title&direction=asc&"' in content
