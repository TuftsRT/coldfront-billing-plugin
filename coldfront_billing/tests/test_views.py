import pytest
from django.urls import reverse

from .conftest import create_pi_user, create_project_with_billing_user


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

    def test_superuser_sees_all_projects(self, client, superuser, multiple_projects):
        """Test that superusers can see all projects."""
        response = self._get_billing_response(client, superuser)
        assert response.status_code == 200
        assert len(response.context['project_list']) == 5

    def test_regular_user_without_billing_role_sees_nothing(self, client, user, project):
        """Test that regular users without Billing role see no projects."""
        response = self._get_billing_response(client, user)
        assert response.status_code == 200
        assert len(response.context['project_list']) == 0

    def test_regular_user_with_billing_role_sees_projects(self, client, user, project_with_billing_user):
        """Test that users with Billing role can see their projects."""
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
        db,
    ):
        """Test that only Active ProjectUser status is shown."""
        pi_user1 = create_pi_user('1')
        active_project = create_project_with_billing_user(
            user, pi_user1, project_status_active, billing_role, project_user_status_active, 'Active User Project'
        )

        pi_user2 = create_pi_user('2')
        inactive_project = create_project_with_billing_user(
            user, pi_user2, project_status_active, billing_role, project_user_status_inactive, 'Inactive User Project'
        )

        response = self._get_billing_response(client, user)
        assert response.status_code == 200
        project_ids = [p.id for p in response.context['project_list']]
        assert active_project.id in project_ids
        assert inactive_project.id not in project_ids

    def test_ordering(self, client, superuser, multiple_projects):
        """Test that ordering by different fields works."""
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

    def test_context_includes_cost_and_cost_centers(self, client, superuser, project):
        """Test that each project in context has cost and cost_centers."""
        response = self._get_billing_response(client, superuser)
        assert response.status_code == 200
        for project_obj in response.context['project_list']:
            assert hasattr(project_obj, 'cost')
            assert project_obj.cost.startswith('$')
            cost_value = int(project_obj.cost.replace('$', ''))
            assert 100 <= cost_value <= 1000
            assert hasattr(project_obj, 'cost_centers')
            assert project_obj.cost_centers == '-'
