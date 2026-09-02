"""Tests for the billing_code_report view, exercised through the real URL/client
stack (permission decorator, URL routing, form validation, and template/JSON
rendering all included).
"""

from decimal import Decimal

import pytest
from coldfront.core.project.models import Project
from django.urls import reverse

from coldfront_billing.tests.conftest import add_storage_allocation_to_project, create_pi_user


def _report_url(**params):
    url = reverse('missing-billing-code-report')
    if params:
        query = '&'.join(f'{key}={value}' for key, value in params.items())
        url = f'{url}?{query}'
    return url


@pytest.mark.django_db
@pytest.mark.usefixtures('configure_urls')
class TestBillingCodeReportAccess:
    def test_anonymous_user_redirected_to_login(self, client):
        response = client.get(_report_url())

        assert response.status_code == 302
        assert '/login' in response.url

    def test_regular_user_without_billing_perm_redirected_to_login(self, client, user):
        client.force_login(user)
        response = client.get(_report_url())

        assert response.status_code == 302
        assert '/login' in response.url

    def test_pi_user_can_access_report(
        self, client, project, storage_resource_type, allocation_status_active,
        cost_attribute_type, quota_attribute_type,
    ):
        add_storage_allocation_to_project(
            project, storage_resource_type, allocation_status_active,
            cost_attribute_type, quota_attribute_type,
        )
        client.force_login(project.pi)
        response = client.get(_report_url())

        assert response.status_code == 200
        assert response.context['missing_billing_code']

    def test_billing_role_user_can_access_report(self, client, user, project_with_billing_user):
        client.force_login(user)
        response = client.get(_report_url())

        assert response.status_code == 200
        assert 'missing_billing_code' in response.context
        assert 'total_cost' in response.context

    def test_billing_role_user_sees_their_project_though_not_the_pi(self, client, user, project_with_billing_user):
        """A user with the Billing/Manager project role (not the PI) must still
        see that project's billing data, since has_billing_perm grants them access."""
        client.force_login(user)
        response = client.get(_report_url())

        assert response.status_code == 200
        assert len(response.context['missing_billing_code']) == 1
        assert response.context['missing_billing_code'][0]['project'] == project_with_billing_user

    def test_billing_role_user_ignores_username_param_and_sees_only_visible_project(
        self, client, user, project_with_billing_user, superuser, project,
        storage_resource_type, allocation_status_active, cost_attribute_type,
        quota_attribute_type,
    ):
        """Non-superuser requests are always scoped to the user's own visible
        projects, regardless of what's passed in the query string."""
        unrelated_pi = create_pi_user('_unrelated')
        unrelated_project = Project.objects.create(
            title='Unrelated PI Project',
            pi=unrelated_pi,
            status=project.status,
            field_of_science=project.field_of_science,
        )
        add_storage_allocation_to_project(
            unrelated_project, storage_resource_type, allocation_status_active,
            cost_attribute_type, quota_attribute_type,
            resource_name='Unrelated Project Storage',
        )
        client.force_login(user)
        response = client.get(_report_url(username=superuser.username))

        assert response.status_code == 200
        projects = [entry['project'] for entry in response.context['missing_billing_code']]
        assert projects == [project_with_billing_user]
        assert unrelated_project not in projects

    def test_billing_role_user_does_not_get_filter_form_in_context(self, client, user, project_with_billing_user):
        client.force_login(user)
        response = client.get(_report_url())

        assert response.status_code == 200
        assert 'form' not in response.context


@pytest.mark.django_db
@pytest.mark.usefixtures('configure_urls')
class TestBillingCodeReportSuperuser:
    def test_superuser_sees_projects_missing_billing_codes(
        self, client, superuser, project, storage_resource_type, allocation_status_active,
        cost_attribute_type, quota_attribute_type,
    ):
        add_storage_allocation_to_project(
            project, storage_resource_type, allocation_status_active,
            cost_attribute_type, quota_attribute_type,
            cost_value='100', quota_value='5',
        )
        client.force_login(superuser)
        response = client.get(_report_url())

        assert response.status_code == 200
        assert len(response.context['missing_billing_code']) == 1
        assert response.context['missing_billing_code'][0]['project'] == project
        assert response.context['total_cost'] == Decimal('500.00')
        assert response.context['form'] is not None

    def test_superuser_excludes_projects_with_cost_center_assignment(
        self, client, superuser, project, cost_center_assignment, storage_resource_type,
        allocation_status_active, cost_attribute_type, quota_attribute_type,
    ):
        add_storage_allocation_to_project(
            project, storage_resource_type, allocation_status_active,
            cost_attribute_type, quota_attribute_type,
        )
        client.force_login(superuser)
        response = client.get(_report_url())

        assert response.status_code == 200
        assert response.context['missing_billing_code'] == []

    def test_superuser_can_filter_by_username(
        self, client, superuser, project, storage_resource_type, allocation_status_active,
        cost_attribute_type, quota_attribute_type,
    ):
        add_storage_allocation_to_project(
            project, storage_resource_type, allocation_status_active,
            cost_attribute_type, quota_attribute_type,
        )
        client.force_login(superuser)
        response = client.get(_report_url(username='definitely-no-match'))

        assert response.status_code == 200
        assert response.context['missing_billing_code'] == []

    def test_superuser_json_format_returns_serialized_payload(
        self, client, superuser, project, storage_resource_type, allocation_status_active,
        cost_attribute_type, quota_attribute_type,
    ):
        add_storage_allocation_to_project(
            project, storage_resource_type, allocation_status_active,
            cost_attribute_type, quota_attribute_type,
            cost_value='100', quota_value='5',
        )
        client.force_login(superuser)
        response = client.get(_report_url(format='json'))

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json'
        payload = response.json()
        assert payload['month']
        assert payload['total_cost'] == '500.00'
        assert payload['missing_billing_code'] == [{
            'project_id': project.id,
            'project_title': project.title,
            'pi_username': project.pi.username,
            'project_cost': '500.00',
        }]

    def test_superuser_json_format_with_no_results(self, client, superuser, storage_resource_type):
        client.force_login(superuser)
        response = client.get(_report_url(format='json'))

        assert response.status_code == 200
        assert response.json()['missing_billing_code'] == []

    def test_superuser_invalid_form_data_returns_400(self, client, superuser):
        client.force_login(superuser)
        response = client.get(_report_url(username='a' * 60))

        assert response.status_code == 400
        assert response.context['message'] == 'Invalid form data.'
