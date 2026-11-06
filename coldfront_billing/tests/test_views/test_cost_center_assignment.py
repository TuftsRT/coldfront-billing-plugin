import json

import pytest
from django.urls import reverse


@pytest.mark.django_db
@pytest.mark.usefixtures("configure_urls")
class TestCostCenterAssignmentUpdateView:
    """Test suite for CostCenterAssignmentUpdateView."""

    @staticmethod
    def _post_cost_center_assignment(client, user, project_id, assignments_data):
        """Helper method to post cost center assignment update."""
        client.force_login(user)
        url = reverse("update_cost_center_assignment")
        data = {"project_id": project_id, "assignments": json.dumps(assignments_data)}
        return client.post(url, data=data)

    def test_unauthenticated_user_redirected(self, client, project):
        """Test that unauthenticated users are redirected to login."""
        url = reverse("update_cost_center_assignment")
        response = client.post(url, data={})
        assert response.status_code == 302
        assert "/login" in response.url

    def test_superuser_can_update_any_project(self, client, superuser, project):
        """Test that superusers can update cost center assignments for any project."""
        from coldfront_billing.models import CostCenter

        CostCenter.objects.create(name="DEPT001", cost_center_type="department")

        assignments_data = [{"department": "DEPT001", "percentage": 100}]

        response = self._post_cost_center_assignment(client, superuser, project.id, assignments_data)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert "Cost center assignment updated successfully" in response_data["message"]
        assert response_data["assignments"] == assignments_data

    def test_regular_user_without_billing_role_forbidden(self, client, user, project):
        """Test that users without Billing role cannot update cost center assignments."""
        from coldfront_billing.models import CostCenter

        CostCenter.objects.create(name="DEPT003", cost_center_type="department")

        assignments_data = [{"department": "DEPT003", "percentage": 100}]

        response = self._post_cost_center_assignment(client, user, project.id, assignments_data)

        assert response.status_code == 403
        response_data = response.json()
        assert response_data["success"] is False
        assert "You do not have permission" in response_data["error"]

    def test_regular_user_with_manager_role_can_update(self, client, user, project_with_manager_user):
        """Test that users with Manager role can update cost center assignments."""
        from coldfront_billing.models import CostCenter

        CostCenter.objects.create(name="DEPT_MGR", cost_center_type="department")

        assignments_data = [{"department": "DEPT_MGR", "percentage": 100}]

        response = self._post_cost_center_assignment(client, user, project_with_manager_user.id, assignments_data)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert "Cost center assignment updated successfully" in response_data["message"]
        assert response_data["assignments"] == assignments_data

    def test_update_existing_cost_center_assignment_success(self, client, superuser, project):
        """Test updating an existing cost center assignment."""
        from coldfront_billing.models import CostCenter, CostCenterAssignment

        CostCenter.objects.create(name="DEPT004", cost_center_type="department")
        CostCenter.objects.create(name="DEPT005", cost_center_type="department")

        initial_assignments = [{"department": "DEPT004", "percentage": 100}]
        CostCenterAssignment.objects.create(project=project, assignments=initial_assignments)

        new_assignments = [
            {"department": "DEPT004", "percentage": 60},
            {"department": "DEPT005", "percentage": 40},
        ]

        response = self._post_cost_center_assignment(client, superuser, project.id, new_assignments)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["assignments"] == new_assignments

        assignment = CostCenterAssignment.objects.get(project=project)
        assert assignment.assignments == new_assignments

    def test_invalid_json_format_returns_error(self, client, superuser, project):
        """Test that invalid JSON format returns validation error."""
        client.force_login(superuser)
        url = reverse("update_cost_center_assignment")

        # Send invalid JSON
        data = {"project_id": project.id, "assignments": "invalid-json-string"}

        response = client.post(url, data=data)

        assert response.status_code == 400
        response_data = response.json()
        assert response_data["success"] is False
        assert "errors" in response_data

    def test_nonexistent_cost_center_returns_error(self, client, superuser, project):
        """Test that referencing nonexistent cost center returns validation error."""
        assignments_data = [{"department": "NONEXISTENT", "percentage": 100}]

        response = self._post_cost_center_assignment(client, superuser, project.id, assignments_data)

        assert response.status_code == 400
        response_data = response.json()
        assert response_data["success"] is False
        assert "errors" in response_data

    def test_missing_project_id_field_returns_error(self, client, superuser, project):
        """Test that missing project_id field returns validation error."""
        from coldfront_billing.models import CostCenter

        CostCenter.objects.create(name="DEPT008", cost_center_type="department")
        client.force_login(superuser)
        url = reverse("update_cost_center_assignment")

        # Missing project_id field
        data = {"assignments": json.dumps([{"department": "DEPT008", "percentage": 100}])}

        response = client.post(url, data=data)

        assert response.status_code == 400
        response_data = response.json()
        assert response_data["success"] is False
        assert "errors" in response_data

    def test_missing_assignments_field_returns_error(self, client, superuser, project):
        """Test that missing assignments field returns validation error."""
        client.force_login(superuser)
        url = reverse("update_cost_center_assignment")

        # Missing assignments field
        data = {"project_id": project.id}

        response = client.post(url, data=data)

        assert response.status_code == 400
        response_data = response.json()
        assert response_data["success"] is False
        assert "errors" in response_data

    def test_multiple_cost_centers_assignment(self, client, superuser, project):
        """Test assigning multiple cost centers with different percentages."""
        from coldfront_billing.models import CostCenter

        for dept_id in ("DEPT009", "DEPT010", "DEPT011"):
            CostCenter.objects.create(name=dept_id, cost_center_type="department")

        assignments_data = [
            {"department": "DEPT009", "percentage": 50},
            {"department": "DEPT010", "percentage": 30},
            {"department": "DEPT011", "percentage": 20},
        ]

        response = self._post_cost_center_assignment(client, superuser, project.id, assignments_data)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["assignments"] == assignments_data

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

        CostCenter.objects.create(name="DEPT013", cost_center_type="department")
        assignments_data = [{"department": "DEPT013", "percentage": 100}]

        response = self._post_cost_center_assignment(client, user, project.id, assignments_data)

        assert response.status_code == 403
        response_data = response.json()
        assert response_data["success"] is False
        assert "You do not have permission" in response_data["error"]

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

        CostCenter.objects.create(name="DEPT_MGR_INACTIVE", cost_center_type="department")
        assignments_data = [{"department": "DEPT_MGR_INACTIVE", "percentage": 100}]

        response = self._post_cost_center_assignment(client, user, project.id, assignments_data)

        assert response.status_code == 403
        response_data = response.json()
        assert response_data["success"] is False
        assert "You do not have permission" in response_data["error"]

    def test_assignments_invalid_top_level_type_returns_error(self, client, superuser, project):
        """Test that assignments JSON must be a list or legacy object map."""
        client.force_login(superuser)
        url = reverse("update_cost_center_assignment")

        data = {"project_id": project.id, "assignments": json.dumps(42)}

        response = client.post(url, data=data)

        assert response.status_code == 400
        response_data = response.json()
        assert response_data["success"] is False
        assert "errors" in response_data

    def test_get_request_not_allowed(self, client, superuser, project):
        """Test that GET requests are not allowed (only POST)."""
        client.force_login(superuser)
        url = reverse("update_cost_center_assignment")

        response = client.get(url)

        # Should return 405 Method Not Allowed since view only accepts POST
        assert response.status_code == 405

    def test_cost_center_assignment_created_if_not_exists(self, client, superuser, project):
        """Test that CostCenterAssignment is created if it doesn't exist."""
        from coldfront_billing.models import CostCenter, CostCenterAssignment

        # Ensure no assignment exists initially
        assert not CostCenterAssignment.objects.filter(project=project).exists()

        CostCenter.objects.create(name="DEPT015", cost_center_type="department")
        assignments_data = [{"department": "DEPT015", "percentage": 100}]

        response = self._post_cost_center_assignment(client, superuser, project.id, assignments_data)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True

        assert CostCenterAssignment.objects.filter(project=project).exists()
        assignment = CostCenterAssignment.objects.get(project=project)
        assert assignment.assignments == assignments_data


@pytest.mark.django_db
@pytest.mark.usefixtures("configure_urls")
class TestGrantFieldInCostCenterAssignments:
    """Grant is optional per row; empty values must not appear in stored JSON."""

    @staticmethod
    def _post_cost_center_assignment(client, user, project_id, assignments_data):
        client.force_login(user)
        url = reverse("update_cost_center_assignment")
        data = {"project_id": project_id, "assignments": json.dumps(assignments_data)}
        return client.post(url, data=data)

    def test_update_with_grant_succeeds(self, client, superuser, project):
        from coldfront_billing.models import CostCenter, CostCenterAssignment

        CostCenter.objects.create(name="DEPT_GRANT_A", cost_center_type="department")
        CostCenter.objects.create(name="GRANT-XYZ", cost_center_type="grant")

        assignments_data = [{"department": "DEPT_GRANT_A", "percentage": 100, "grant": "GRANT-XYZ"}]

        response = self._post_cost_center_assignment(client, superuser, project.id, assignments_data)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["assignments"] == assignments_data

        assignment = CostCenterAssignment.objects.get(project=project)
        assert assignment.assignments == assignments_data
        assert "grant" in assignment.assignments[0]

    def test_split_assignment_grant_only_on_one_row(self, client, superuser, project):
        from coldfront_billing.models import CostCenter, CostCenterAssignment

        for name, ctype in (
            ("DEPT_G1", "department"),
            ("DEPT_G2", "department"),
            ("GRANT-SPLIT", "grant"),
        ):
            CostCenter.objects.create(name=name, cost_center_type=ctype)

        expected = [
            {"department": "DEPT_G1", "percentage": 60, "grant": "GRANT-SPLIT"},
            {"department": "DEPT_G2", "percentage": 40},
        ]

        response = self._post_cost_center_assignment(client, superuser, project.id, expected)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["assignments"] == expected

        stored = CostCenterAssignment.objects.get(project=project).assignments
        assert stored == expected
        assert "grant" in stored[0]
        assert "grant" not in stored[1]

    def test_empty_grant_string_omitted_from_stored_json(self, client, superuser, project):
        from coldfront_billing.models import CostCenter, CostCenterAssignment

        CostCenter.objects.create(name="DEPT_NO_GRANT", cost_center_type="department")

        payload = [{"department": "DEPT_NO_GRANT", "percentage": 100, "grant": ""}]
        expected_stored = [{"department": "DEPT_NO_GRANT", "percentage": 100}]

        response = self._post_cost_center_assignment(client, superuser, project.id, payload)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["assignments"] == expected_stored

        assignment = CostCenterAssignment.objects.get(project=project)
        assert assignment.assignments == expected_stored
        assert "grant" not in assignment.assignments[0]

    def test_null_grant_in_json_omitted_from_stored_json(self, client, superuser, project):
        from coldfront_billing.models import CostCenter, CostCenterAssignment

        CostCenter.objects.create(name="DEPT_NULL_GRANT", cost_center_type="department")

        payload = [{"department": "DEPT_NULL_GRANT", "percentage": 100, "grant": None}]
        expected_stored = [{"department": "DEPT_NULL_GRANT", "percentage": 100}]

        response = self._post_cost_center_assignment(client, superuser, project.id, payload)

        assert response.status_code == 200
        assert response.json()["assignments"] == expected_stored
        assert "grant" not in CostCenterAssignment.objects.get(project=project).assignments[0]

    def test_unknown_grant_returns_validation_error(self, client, superuser, project):
        from coldfront_billing.models import CostCenter

        CostCenter.objects.create(name="DEPT_OK", cost_center_type="department")

        assignments_data = [{"department": "DEPT_OK", "percentage": 100, "grant": "UNKNOWN_GRANT_CODE"}]

        response = self._post_cost_center_assignment(client, superuser, project.id, assignments_data)

        assert response.status_code == 400
        response_data = response.json()
        assert response_data["success"] is False
        assert "errors" in response_data
        assert "Unknown grant" in str(response_data["errors"])

    def test_grant_autocomplete_short_query_returns_empty(self, client, superuser):
        from coldfront_billing.models import CostCenter

        CostCenter.objects.create(name="GRANT-SHORT", cost_center_type="grant")
        client.force_login(superuser)
        url = reverse("autocomplete_cost_center")
        response = client.get(url, {"q": "GR", "type": "grant"})
        assert response.status_code == 200
        assert response.json()["results"] == []

    def test_grant_autocomplete_lists_only_grant_type_cost_centers(self, client, superuser):
        from coldfront_billing.models import CostCenter

        CostCenter.objects.create(name="GRANT-FUND-001", cost_center_type="grant")
        CostCenter.objects.create(name="GRANT-FUND-002", cost_center_type="grant")
        CostCenter.objects.create(name="GRANT-LIKE-DEPT", cost_center_type="department")

        client.force_login(superuser)
        url = reverse("autocomplete_cost_center")
        response = client.get(url, {"q": "GRA", "type": "grant"})
        assert response.status_code == 200
        assert response.json()["results"] == ["GRANT-FUND-001", "GRANT-FUND-002"]
