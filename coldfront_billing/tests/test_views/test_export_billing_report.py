"""Tests for ExportBillingReportView (CSV billing report)."""

import csv
from io import StringIO
from unittest.mock import patch

import pytest
from coldfront.core.project.models import Project
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from coldfront_billing.models import BillingScheduleSettings, CostCenterAssignment
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

    def test_auto_assign_when_setting_enabled(self, client, superuser):
        BillingScheduleSettings.objects.create(
            start_date=timezone.localdate(),
            autoassign_no_cost_quota=True,
        )
        client.force_login(superuser)
        with (
            patch('coldfront_billing.views.reports.csv.auto_assign_quota') as mock_auto_assign,
            patch(
                'coldfront_billing.views.reports.csv.create_csv_report',
                return_value=('billing.csv', 'h1\n'),
            ),
        ):
            response = client.get(reverse('reports_export'))
        assert response.status_code == 200
        mock_auto_assign.assert_called_once()

    def test_no_auto_assign_when_setting_disabled(self, client, superuser):
        BillingScheduleSettings.objects.create(
            start_date=timezone.localdate(),
            autoassign_no_cost_quota=False,
        )
        client.force_login(superuser)
        with (
            patch('coldfront_billing.views.reports.csv.auto_assign_quota') as mock_auto_assign,
            patch(
                'coldfront_billing.views.reports.csv.create_csv_report',
                return_value=('billing.csv', 'h1\n'),
            ),
        ):
            response = client.get(reverse('reports_export'))
        assert response.status_code == 200
        mock_auto_assign.assert_not_called()

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
        assert rows[1] == ['ACC1', 'DEPT_A', 'DEPT_X', '300.00', desc]
        assert rows[2] == ['ACC1', 'DEPT_B', '', '200.00', desc]
        assert rows[3] == ['ACC1', 'C800260', '', '-500.00', 'MAR-PRE-Storage Charges']

    def test_superuser_csv_single_total_row_for_multiple_projects(
        self,
        client,
        superuser,
        project,
        pi_user,
        project_status_active,
        field_of_science,
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

        pi_user_two = User.objects.create_user(username='pi_two', email='pi2@example.com', password='pass')
        project_two = Project.objects.create(
            title='Second Project',
            pi=pi_user_two,
            status=project_status_active,
            field_of_science=field_of_science,
        )
        add_storage_allocation_to_project(
            project_two,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            cost_value='100',
            quota_value='3',
            resource_name='Second Project Storage',
        )
        CostCenterAssignment.objects.create(
            project=project_two,
            assignments=[{'department': 'DEPT_C', 'percentage': 100}],
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
        desc_one = f'MAR-PRE-{pi_user.username}-{project.title}'
        desc_two = f'MAR-PRE-{pi_user_two.username}-{project_two.title}'

        project_one_rows = [row for row in rows[1:] if row[4] == desc_one]
        project_two_rows = [row for row in rows[1:] if row[4] == desc_two]
        assert project_one_rows == [
            ['ACC1', 'DEPT_A', 'DEPT_X', '300.00', desc_one],
            ['ACC1', 'DEPT_B', '', '200.00', desc_one],
        ]
        assert project_two_rows == [['ACC1', 'DEPT_C', '', '300.00', desc_two]]

        total_rows = [row for row in rows if row[1] == 'C800260']
        assert len(total_rows) == 1
        assert total_rows[0] == ['ACC1', 'C800260', '', '-800.00', 'MAR-PRE-Storage Charges']
        assert rows[-1] == total_rows[0]

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
        assert len(rows) == 2
        assert rows[0][0] == 'Account'
        assert rows[1][3] == '-0.00'

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
        assert len(rows) == 2
        assert rows[1][3] == '-0.00'
