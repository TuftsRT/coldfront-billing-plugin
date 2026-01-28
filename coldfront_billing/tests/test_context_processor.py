import pytest
from django.contrib.auth.models import AnonymousUser

from coldfront_billing.context_processor import billing_role

from .conftest import create_billing_request, create_pi_user, create_project_with_billing_user


@pytest.mark.django_db
class TestBillingRoleContextProcessor:
    """Test suite for billing_role context processor."""

    def test_unauthenticated_user_returns_empty_dict(self):
        """Test that unauthenticated users return empty dict."""
        request = create_billing_request(AnonymousUser())
        result = billing_role(request)
        assert result == {}

    def test_superuser_returns_has_billing_role_true(self, superuser):
        """Test that superusers return has_billing_role=True."""
        request = create_billing_request(superuser)
        result = billing_role(request)
        assert result == {'has_billing_role': True}

    def test_regular_user_without_billing_role_returns_false(self, user, project):
        """Test that regular users without Billing role return False."""
        request = create_billing_request(user)
        result = billing_role(request)
        assert result == {'has_billing_role': False}

    def test_user_with_active_billing_role_returns_true(self, user, project_with_billing_user):
        """Test that users with active Billing role return True."""
        request = create_billing_request(user)
        result = billing_role(request)
        assert result == {'has_billing_role': True}

    def test_only_active_and_archived_projects_considered(
        self,
        user,
        project_status_active,
        project_status_archived,
        project_status_new,
        billing_role,
        project_user_status_active,
        db,
    ):
        """Test that only Active/Archived projects are considered, not New ones."""
        pi_user1 = create_pi_user('1')
        create_project_with_billing_user(
            user, pi_user1, project_status_active, billing_role, project_user_status_active, 'Active Project'
        )

        pi_user2 = create_pi_user('2')
        create_project_with_billing_user(
            user, pi_user2, project_status_archived, billing_role, project_user_status_active, 'Archived Project'
        )

        pi_user3 = create_pi_user('3')
        create_project_with_billing_user(
            user, pi_user3, project_status_new, billing_role, project_user_status_active, 'New Project'
        )

        request = create_billing_request(user)
        result = billing_role(request)
        # Should return True because of active/archived projects
        assert result == {'has_billing_role': True}

    def test_only_active_project_user_status_considered(
        self,
        user,
        project_status_active,
        billing_role,
        project_user_status_active,
        project_user_status_inactive,
        db,
    ):
        """Test that only Active ProjectUser status is considered."""
        pi_user1 = create_pi_user('1')
        create_project_with_billing_user(
            user, pi_user1, project_status_active, billing_role, project_user_status_active, 'Active User Project'
        )

        pi_user2 = create_pi_user('2')
        create_project_with_billing_user(
            user, pi_user2, project_status_active, billing_role, project_user_status_inactive, 'Inactive User Project'
        )

        request = create_billing_request(user)
        result = billing_role(request)
        # Should return True because of the active project user
        assert result == {'has_billing_role': True}

    def test_inactive_project_user_returns_false(
        self,
        user,
        project_status_active,
        billing_role,
        project_user_status_inactive,
        db,
    ):
        """Test that inactive ProjectUser status returns False."""
        pi_user = create_pi_user('1')
        create_project_with_billing_user(
            user,
            pi_user,
            project_status_active,
            billing_role,
            project_user_status_inactive,
            'Project with Inactive User',
        )

        request = create_billing_request(user)
        result = billing_role(request)
        assert result == {'has_billing_role': False}
