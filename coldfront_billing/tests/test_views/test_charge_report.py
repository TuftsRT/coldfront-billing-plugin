"""Tests for the charge_report view, exercised through the real URL/client
stack (permission decorator, URL routing, form validation, and
template/JSON/CSV rendering all included).
"""

from decimal import Decimal

import pytest
from coldfront.core.project.models import Project
from django.urls import reverse

from coldfront_billing.models import CostCenterAssignment
from coldfront_billing.tests.conftest import add_storage_allocation_to_project, create_pi_user


def _report_url(**params):
    url = reverse('charge-report')
    if params:
        query = '&'.join(f'{key}={value}' for key, value in params.items())
        url = f'{url}?{query}'
    return url


@pytest.mark.django_db
@pytest.mark.usefixtures('configure_urls')
class TestChargeReportAccess:
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
        # no CostCenterAssignment yet, so the cost isn't split into charge_report rows
        assert response.context['charge_report'] == []
        assert response.context['total_cost']

    def test_billing_role_user_can_access_report(self, client, user, project_with_billing_user):
        client.force_login(user)
        response = client.get(_report_url())

        assert response.status_code == 200
        assert 'charge_report' in response.context
        assert 'total_cost' in response.context

    def test_billing_role_user_sees_their_project_though_not_the_pi(
        self, client, user, project_with_billing_user, cost_center_assignment,
    ):
        """A user with the Billing/Manager project role (not the PI) must still
        see that project's charge data, since has_billing_perm grants them access."""
        client.force_login(user)
        response = client.get(_report_url())

        assert response.status_code == 200
        projects = [entry['project'] for entry in response.context['charge_report']]
        assert projects == [project_with_billing_user]

    def test_billing_role_user_scoped_to_own_visible_projects_only(
        self, client, user, project_with_billing_user, cost_center_assignment, project,
        storage_resource_type, allocation_status_active, cost_attribute_type,
        quota_attribute_type,
    ):
        unrelated_pi = create_pi_user('_unrelated_charge')
        unrelated_project = Project.objects.create(
            title='Unrelated PI Charge Project',
            pi=unrelated_pi,
            status=project.status,
            field_of_science=project.field_of_science,
        )
        add_storage_allocation_to_project(
            unrelated_project, storage_resource_type, allocation_status_active,
            cost_attribute_type, quota_attribute_type,
            resource_name='Unrelated Charge Storage',
        )
        CostCenterAssignment.objects.create(
            project=unrelated_project, assignments=[{'department': 'OTHER_DEPT', 'percentage': 100}]
        )
        client.force_login(user)
        response = client.get(_report_url())

        assert response.status_code == 200
        projects = {entry['project'] for entry in response.context['charge_report']}
        assert projects == {project_with_billing_user}
        assert unrelated_project not in projects

    def test_non_superuser_does_not_see_username_filter_in_form(self, client, user, project_with_billing_user):
        client.force_login(user)
        response = client.get(_report_url())

        assert response.status_code == 200
        assert 'form' in response.context

    def test_non_superuser_invalid_billing_code_returns_400(self, client, user, project_with_billing_user):
        client.force_login(user)
        response = client.get(_report_url(billing_code='a' * 60))

        assert response.status_code == 400
        assert response.context['message'] == 'Invalid form data.'


@pytest.mark.django_db
@pytest.mark.usefixtures('configure_urls')
class TestChargeReportSuperuser:
    def test_superuser_sees_charge_report_split_by_department(
        self, client, superuser, project, cost_center_assignment,
        storage_resource_type, allocation_status_active, cost_attribute_type,
        quota_attribute_type,
    ):
        CostCenterAssignment.objects.filter(project=project).update(
            assignments=[
                {'department': 'DEPT001', 'percentage': 60},
                {'department': 'DEPT002', 'percentage': 40},
            ]
        )
        add_storage_allocation_to_project(
            project, storage_resource_type, allocation_status_active,
            cost_attribute_type, quota_attribute_type,
            cost_value='20', quota_value='10',
        )
        client.force_login(superuser)
        response = client.get(_report_url())

        assert response.status_code == 200
        cost_by_department = {row['department']: row['charged_to_id'] for row in response.context['charge_report']}
        assert cost_by_department == {'DEPT001': Decimal('120.00'), 'DEPT002': Decimal('80.01')}
        assert response.context['total_cost'] == Decimal('200.00')
        assert response.context['form'] is not None

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
        # projects without a CostCenterAssignment don't produce charge_report rows,
        # but their cost is still counted toward total_cost
        assert response.context['charge_report'] == []
        assert response.context['total_cost'] == Decimal('500.00')

    def test_superuser_can_filter_by_username(
        self, client, superuser, project, cost_center_assignment,
        storage_resource_type, allocation_status_active, cost_attribute_type,
        quota_attribute_type,
    ):
        add_storage_allocation_to_project(
            project, storage_resource_type, allocation_status_active,
            cost_attribute_type, quota_attribute_type,
        )
        client.force_login(superuser)
        response = client.get(_report_url(username='definitely-no-match'))

        assert response.status_code == 200
        assert response.context['charge_report'] == []
        assert response.context['total_cost'] == Decimal('0.00')

    def test_superuser_can_filter_by_billing_code(
        self, client, superuser, project, cost_center_assignment,
        storage_resource_type, allocation_status_active, cost_attribute_type,
        quota_attribute_type,
    ):
        add_storage_allocation_to_project(
            project, storage_resource_type, allocation_status_active,
            cost_attribute_type, quota_attribute_type,
        )
        client.force_login(superuser)
        response = client.get(_report_url(billing_code='NO_SUCH_DEPT'))

        assert response.status_code == 200
        assert response.context['charge_report'] == []

    def test_superuser_can_filter_by_username_and_billing_code_together(
        self, client, superuser, project, cost_center_assignment,
        storage_resource_type, allocation_status_active, cost_attribute_type,
        quota_attribute_type,
    ):
        """Regression test: this combined-filter branch used to crash with a
        FieldError (`project__pi__username__istartswith` isn't a valid lookup
        on Project)."""
        add_storage_allocation_to_project(
            project, storage_resource_type, allocation_status_active,
            cost_attribute_type, quota_attribute_type,
        )
        client.force_login(superuser)
        response = client.get(_report_url(username=project.pi.username, billing_code='ASSIGN_DEPT'))

        assert response.status_code == 200
        assert len(response.context['charge_report']) == 1
        assert response.context['charge_report'][0]['project'] == project

    def test_superuser_invalid_form_data_returns_400(self, client, superuser):
        client.force_login(superuser)
        response = client.get(_report_url(username='a' * 60))

        assert response.status_code == 400
        assert response.context['message'] == 'Invalid form data.'

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
        assert payload['charge_report'] == []
        assert payload['missing_billing_codes'] == [{
            'project_id': project.id,
            'project': project.title,
            'owner': project.pi.username,
            'project_cost': '500.00',
        }]

    def test_superuser_json_format_with_no_results(self, client, superuser, storage_resource_type):
        client.force_login(superuser)
        response = client.get(_report_url(format='json'))

        assert response.status_code == 200
        payload = response.json()
        assert payload['charge_report'] == []
        assert payload['missing_billing_codes'] == []

    def test_superuser_csv_format_returns_attachment(
        self, client, superuser, project, cost_center_assignment,
        storage_resource_type, allocation_status_active, cost_attribute_type,
        quota_attribute_type,
    ):
        add_storage_allocation_to_project(
            project, storage_resource_type, allocation_status_active,
            cost_attribute_type, quota_attribute_type,
            cost_value='100', quota_value='5',
        )
        client.force_login(superuser)
        response = client.get(_report_url(format='csv'))

        assert response.status_code == 200
        assert response['Content-Type'] == 'text/csv'
        assert 'attachment; filename="charge_report_' in response['Content-Disposition']
        content = response.content.decode()
        assert 'DeptId,Project Number,Cost,Project Description,UTLN,Full Name' in content
        assert 'ASSIGN_DEPT' in content
        assert project.title in content
        assert project.pi.username in content
