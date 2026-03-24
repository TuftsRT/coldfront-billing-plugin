import json

import pytest
from django.urls import reverse


@pytest.mark.django_db
@pytest.mark.usefixtures('configure_urls')
class TestCostCenterAssignmentUpdateView:
    """Test suite for CostCenterAssignmentUpdateView."""

    @staticmethod
    def _post_cost_center_assignment(client, user, project_id, assignments_data):
        """Helper method to post cost center assignment update."""
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

    def test_regular_user_with_manager_role_can_update(self, client, user, project_with_manager_user):
        """Test that users with Manager role can update cost center assignments."""
        from coldfront_billing.models import CostCenter

        CostCenter.objects.create(dept_id='DEPT_MGR')

        assignments_data = {'DEPT_MGR': 100}

        response = self._post_cost_center_assignment(client, user, project_with_manager_user.id, assignments_data)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data['success'] is True
        assert 'Cost center assignment updated successfully' in response_data['message']
        assert response_data['assignments'] == assignments_data

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

    def test_inactive_manager_user_forbidden(self, client, user, project, manager_role, project_user_status_inactive):
        """Test that users with Inactive Manager role cannot update cost center assignments."""
        from coldfront.core.project.models import ProjectUser

        from coldfront_billing.models import CostCenter

        ProjectUser.objects.create(
            project=project,
            user=user,
            role=manager_role,
            status=project_user_status_inactive,
        )

        CostCenter.objects.create(dept_id='DEPT_MGR_INACTIVE')
        assignments_data = {'DEPT_MGR_INACTIVE': 100}

        response = self._post_cost_center_assignment(client, user, project.id, assignments_data)

        assert response.status_code == 403
        response_data = response.json()
        assert response_data['success'] is False
        assert 'You do not have permission' in response_data['error']

    def test_assignments_non_dict_format_returns_error(self, client, superuser, project):
        """Test that assignments in non-dictionary format returns validation error."""
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
