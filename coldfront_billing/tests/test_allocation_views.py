"""Unit tests for UpdateAllocationDetailsView and AllocationCreateView."""

import pytest
from django.test import override_settings
from django.urls import reverse

from .conftest import add_storage_allocation_to_project


@pytest.mark.django_db
@pytest.mark.usefixtures('configure_urls')
class TestUpdateAllocationDetailsView:
    """Test suite for UpdateAllocationDetailsView."""

    @staticmethod
    def _get_update_allocation_details(client, user, allocation_pk):
        """Helper to GET the update allocation details page."""
        client.force_login(user)
        url = reverse('update-allocation-details', kwargs={'pk': allocation_pk})
        return client.get(url)

    @staticmethod
    def _post_update_allocation_details(client, user, allocation_pk, data):
        """Helper to POST the update allocation details form."""
        client.force_login(user)
        url = reverse('update-allocation-details', kwargs={'pk': allocation_pk})
        return client.post(url, data=data)

    def test_unauthenticated_user_redirected(
        self,
        client,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """Test that unauthenticated users are redirected to login."""
        allocation, _ = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            with_quota=False,
        )
        url = reverse('update-allocation-details', kwargs={'pk': allocation.pk})
        response = client.get(url)
        assert response.status_code == 302
        assert '/login' in response.url

    def test_superuser_can_view_form(
        self,
        client,
        superuser,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """Test that superusers can view the update allocation details form."""
        allocation, _ = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            with_quota=False,
        )
        response = self._get_update_allocation_details(client, superuser, allocation.pk)
        assert response.status_code == 200
        assert 'allocation' in response.context
        assert response.context['allocation'] == allocation
        assert 'form' in response.context
        assert 'quota_in_terabyte' in response.context['form'].fields
        assert response.context['show_cost_center'] is True

    def test_pi_can_view_form(
        self,
        client,
        pi_user,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        project_user_status_active,
    ):
        """Test that project PI can view the update allocation details form."""
        from coldfront.core.project.models import ProjectUser, ProjectUserRoleChoice

        manager_role, _ = ProjectUserRoleChoice.objects.get_or_create(name='Manager')
        # PI must be in projectuser_set with Active status to have allocation permission
        ProjectUser.objects.create(
            project=project,
            user=pi_user,
            role=manager_role,
            status=project_user_status_active,
        )
        allocation, _ = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            with_quota=False,
        )
        response = self._get_update_allocation_details(client, pi_user, allocation.pk)
        assert response.status_code == 200

    def test_user_without_permission_forbidden(
        self,
        client,
        user,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """Test that users without allocation permission get 403."""
        allocation, _ = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            with_quota=False,
        )
        response = self._get_update_allocation_details(client, user, allocation.pk)
        assert response.status_code == 403

    def test_already_has_quota_redirects_with_info_message(
        self,
        client,
        superuser,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """Test that allocation with quota already set redirects with info message."""
        allocation, _ = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            with_quota=True,
        )
        response = self._get_update_allocation_details(client, superuser, allocation.pk)
        assert response.status_code == 302
        assert response.url == reverse('project-detail', kwargs={'pk': project.pk})

    def test_post_valid_quota_creates_attribute_and_redirects(
        self,
        client,
        superuser,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """Test that valid POST creates quota attribute and redirects to project."""
        from coldfront.core.allocation.models import AllocationAttribute

        allocation, _ = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            with_quota=False,
        )
        data = {'quota_in_terabyte': 10.5}

        response = self._post_update_allocation_details(client, superuser, allocation.pk, data)

        assert response.status_code == 302
        assert response.url == reverse('project-detail', kwargs={'pk': project.pk})

        attr = AllocationAttribute.objects.get(
            allocation=allocation,
            allocation_attribute_type__name='quota_in_terabyte',
        )
        assert attr.value == '10.5'

    def test_post_with_cost_center_creates_assignment(
        self,
        client,
        superuser,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """Test that POST with cost center creates CostCenterAssignment."""
        from coldfront_billing.models import CostCenter, CostCenterAssignment

        CostCenter.objects.create(dept_id='DEPT001')
        allocation, _ = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            with_quota=False,
        )
        data = {'quota_in_terabyte': 5.0, 'cost_center': 'DEPT001'}

        response = self._post_update_allocation_details(client, superuser, allocation.pk, data)

        assert response.status_code == 302
        assignment = CostCenterAssignment.objects.get(project=project)
        assert assignment.assignments == {'DEPT001': 100}

    def test_cost_center_field_hidden_when_project_has_assignment(
        self,
        client,
        superuser,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """Test that cost_center field is hidden when project already has cost center."""
        from coldfront_billing.models import CostCenter, CostCenterAssignment

        CostCenter.objects.create(dept_id='DEPT001')
        CostCenterAssignment.objects.create(project=project, assignments={'DEPT001': 100})
        allocation, _ = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            with_quota=False,
        )

        response = self._get_update_allocation_details(client, superuser, allocation.pk)

        assert response.status_code == 200
        assert 'cost_center' not in response.context['form'].fields
        assert response.context['show_cost_center'] is False

    def test_nonexistent_allocation_returns_404(self, client, superuser):
        """Test that nonexistent allocation returns 404."""
        response = self._get_update_allocation_details(client, superuser, 99999)
        assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.usefixtures('configure_urls')
class TestAllocationCreateView:
    """Test suite for AllocationCreateView (redirect to quota page for paid storage)."""

    @override_settings(INVOICE_ENABLED=False)
    def test_paid_storage_allocation_redirects_to_update_details(
        self,
        client,
        pi_user,
        project,
        storage_resource_type,
        cost_attribute_type,
        project_user_status_active,
    ):
        """Test that creating paid storage allocation redirects to update-allocation-details."""
        from coldfront.core.allocation.models import (
            AllocationStatusChoice,
            AllocationUserStatusChoice,
        )
        from coldfront.core.project.models import ProjectUser, ProjectUserRoleChoice

        # Ensure coldfront-required status choices exist
        AllocationStatusChoice.objects.get_or_create(name='New')
        AllocationUserStatusChoice.objects.get_or_create(name='Active')
        from coldfront.core.resource.models import Resource, ResourceAttribute

        # PI must be Manager on project to create allocations
        manager_role, _ = ProjectUserRoleChoice.objects.get_or_create(name='Manager')
        ProjectUser.objects.create(
            project=project,
            user=pi_user,
            role=manager_role,
            status=project_user_status_active,
        )

        # Create allocatable storage resource with requires_payment
        storage_resource = Resource.objects.create(
            name='Paid Storage',
            resource_type=storage_resource_type,
            requires_payment=True,
            is_allocatable=True,
            is_available=True,
            is_public=True,
        )
        ResourceAttribute.objects.create(
            resource=storage_resource,
            resource_attribute_type=cost_attribute_type,
            value='100',
        )

        client.force_login(pi_user)
        url = reverse('allocation-create', kwargs={'project_pk': project.pk})
        data = {
            'resource': storage_resource.pk,
            'justification': 'Need storage for research',
            'quantity': 1,
            'users': [],
        }

        response = client.post(url, data=data)

        assert response.status_code == 302
        assert 'update-allocation-details' in response.url
        assert '/allocation/' in response.url
        assert '/update-allocation-details/' in response.url
