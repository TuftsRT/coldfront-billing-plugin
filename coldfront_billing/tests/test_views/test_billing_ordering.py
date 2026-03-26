import pytest

from coldfront_billing.tests.conftest import (
    create_pi_user,
    create_project_with_role_user,
)
from coldfront_billing.tests.test_views.common import get_billing_response


@pytest.mark.django_db
@pytest.mark.usefixtures('configure_urls')
class TestBillingViewOrdering:
    """Test suite for BillingView ordering functionality."""

    def test_default_ordering(
        self,
        client,
        superuser,
        multiple_projects,
    ):
        response = get_billing_response(client, superuser)

        assert response.status_code == 200
        project_ids = [p.id for p in response.context['project_list']]
        assert project_ids == sorted(project_ids)

    def test_ascending_ordering_success(
        self,
        client,
        superuser,
        multiple_projects,
    ):
        response = get_billing_response(client, superuser, '?order_by=id&direction=asc')

        assert response.status_code == 200
        project_ids = [p.id for p in response.context['project_list']]
        assert project_ids == sorted(project_ids)

    def test_descending_ordering_success(
        self,
        client,
        superuser,
        multiple_projects,
    ):
        response = get_billing_response(client, superuser, '?order_by=id&direction=des')

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
        response = get_billing_response(client, superuser, '?order_by=title&direction=asc')
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
        response = get_billing_response(client, superuser, '?order_by=title&direction=des')
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
        pi_users = [
            create_pi_user('_zebra'),
            create_pi_user('_alpha'),
            create_pi_user('_beta'),
        ]

        billing_user = create_pi_user('_billing')

        for i, pi_user in enumerate(pi_users):
            create_project_with_role_user(
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

        response = get_billing_response(client, superuser, '?order_by=pi__username&direction=asc')
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
        pi_users = [
            create_pi_user('_alpha'),
            create_pi_user('_beta'),
            create_pi_user('_zebra'),
        ]

        billing_user = create_pi_user('_billing')

        for i, pi_user in enumerate(pi_users):
            create_project_with_role_user(
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

        response = get_billing_response(client, superuser, '?order_by=pi__username&direction=des')
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
        response = get_billing_response(client, superuser, '?order_by=id&direction=invalid')
        assert response.status_code == 200
        project_ids = [p.id for p in response.context['project_list']]
        assert project_ids == sorted(project_ids)
