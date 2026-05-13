import pytest
from django.urls import reverse

from coldfront_billing.tests.conftest import add_storage_allocation_to_project


@pytest.mark.django_db
@pytest.mark.usefixtures('configure_urls')
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

    def test_user_with_manager_role_can_view_project_details(
        self,
        client,
        user,
        project_with_manager_user,
    ):
        """Test that users with Manager role can view their project's billing details."""
        response = self._get_billing_details_response(client, user, project_with_manager_user.id)

        assert response.status_code == 200
        assert response.context['project'] == project_with_manager_user
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
        assert isinstance(response.context['total_cost'], float)
