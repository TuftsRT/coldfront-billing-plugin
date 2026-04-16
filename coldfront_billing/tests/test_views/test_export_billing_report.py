"""Tests for ExportBillingReportView (CSV billing report)."""

import csv
from io import StringIO
from unittest.mock import patch

import pytest
from django.urls import reverse

from coldfront_billing.models import CostCenterAssignment
from coldfront_billing.tests.conftest import add_storage_allocation_to_project
from coldfront_billing.utils import NoStorageException


def _csv_rows(response):
    return list(csv.reader(StringIO(response.content.decode())))


@pytest.mark.django_db
@pytest.mark.usefixtures('configure_urls')
class TestExportBillingReportView:
    def test_anonymous_forbidden(self, client):
        response = client.get(reverse('reports_export'))
        assert response.status_code == 403

    def test_regular_user_forbidden(self, client, user):
        client.force_login(user)
        response = client.get(reverse('reports_export'))
        assert response.status_code == 403
        assert b'not allowed' in response.content.lower()

    def test_superuser_no_storage_returns_404(self, client, superuser):
        client.force_login(superuser)
        with patch(
            'coldfront_billing.prefetch.get_projects_prefetch',
            side_effect=NoStorageException(),
        ):
            response = client.get(reverse('reports_export'))
        assert response.status_code == 404
        assert response.content == b'No storage resource found'

    def test_superuser_csv_rows_match_billing_and_assignments(
        self,
        client,
        superuser,
        project,
        pi_user,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
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
                {'department': 'DEPT_A', 'grant': 'DEPT_X', 'percentage': 60},
                {'department': 'DEPT_B', 'percentage': 40},
            ],
        )

        client.force_login(superuser)
        create_mod = 'coldfront_billing.reports.csv'
        with (
            patch(f'{create_mod}.get_month_abbr', return_value='MAR'),
            patch(f'{create_mod}.ACCOUNT_NAME', 'ACC1'),
            patch(f'{create_mod}.DESCRIPTION_PREFIX', 'PRE'),
        ):
            response = client.get(reverse('reports_export'))

        assert response.status_code == 200

        rows = _csv_rows(response)
        assert rows[0] == ['Account', 'DeptId', 'Project Number', 'Cost', 'Description']

        desc = f'MAR-PRE-{pi_user.username}-{project.title}'
        assert rows[1] == ['ACC1', 'DEPT_A', 'DEPT_X', '$300.0', desc]
        assert rows[2] == ['ACC1', 'DEPT_B', '', '$200.0', desc]

    @patch('coldfront_billing.reports.csv.get_month_abbr', return_value='MAR')
    def test_skips_project_without_cost_center_assignment(
        self,
        _mock_month,
        client,
        superuser,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
        )

        client.force_login(superuser)
        response = client.get(reverse('reports_export'))

        assert response.status_code == 200
        rows = _csv_rows(response)
        assert len(rows) == 1
        assert rows[0][0] == 'Account'

    @patch('coldfront_billing.reports.csv.get_month_abbr', return_value='MAR')
    def test_skips_project_with_zero_total_cost(
        self,
        _mock_month,
        client,
        superuser,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            quota_value='0',
        )
        CostCenterAssignment.objects.create(project=project, assignments=[{'department': 'DEPT_A', 'percentage': 100}])

        client.force_login(superuser)
        response = client.get(reverse('reports_export'))

        assert response.status_code == 200
        rows = _csv_rows(response)
        assert len(rows) == 1
