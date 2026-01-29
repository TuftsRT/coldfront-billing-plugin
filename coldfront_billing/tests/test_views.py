import pytest
from coldfront.core.allocation.models import Allocation, AllocationAttribute
from coldfront.core.resource.models import Resource, ResourceAttribute
from django.test import override_settings
from django.urls import reverse

from .conftest import create_pi_user, create_project_with_billing_user


@pytest.fixture(autouse=True)
def configure_urls():
    """Configure URLs for view tests."""
    with override_settings(ROOT_URLCONF='coldfront_billing.tests.conftest_urls'):
        yield


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

    def test_superuser_sees_all_projects(
        self,
        client,
        superuser,
        multiple_projects,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """Test that superusers can see all projects with Storage allocations."""
        response = self._get_billing_response(client, superuser)
        assert response.status_code == 200
        # All 5 projects should have Storage allocations
        assert len(response.context['project_list']) == 5

    def test_regular_user_without_billing_role_sees_nothing(
        self,
        client,
        user,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """Test that regular users without Billing role see no projects."""
        # Even if project has allocation, user without billing role shouldn't see it
        storage_resource = Resource.objects.create(
            name='Test Storage',
            resource_type=storage_resource_type,
            requires_payment=True,
        )
        ResourceAttribute.objects.create(
            resource=storage_resource,
            resource_attribute_type=cost_attribute_type,
            value='100',
        )
        allocation = Allocation.objects.create(
            project=project,
            status=allocation_status_active,
            quantity=100,
        )
        allocation.resources.add(storage_resource)
        AllocationAttribute.objects.create(
            allocation=allocation,
            allocation_attribute_type=quota_attribute_type,
            value='5',
        )

        response = self._get_billing_response(client, user)
        assert response.status_code == 200
        assert len(response.context['project_list']) == 0

    def test_regular_user_with_billing_role_sees_projects(self, client, user, project_with_billing_user):
        """Test that users with Billing role can see their projects with Storage allocations."""
        # project_with_billing_user fixture already includes Storage allocation
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
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        db,
    ):
        """Test that only Active ProjectUser status is shown."""
        pi_user1 = create_pi_user('1')
        active_project = create_project_with_billing_user(
            user,
            pi_user1,
            project_status_active,
            billing_role,
            project_user_status_active,
            'Active User Project',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
        )

        pi_user2 = create_pi_user('2')
        inactive_project = create_project_with_billing_user(
            user,
            pi_user2,
            project_status_active,
            billing_role,
            project_user_status_inactive,
            'Inactive User Project',
            with_allocation=True,
            storage_resource_type=storage_resource_type,
            allocation_status_active=allocation_status_active,
            cost_attribute_type=cost_attribute_type,
            quota_attribute_type=quota_attribute_type,
        )

        response = self._get_billing_response(client, user)
        assert response.status_code == 200
        project_ids = [p.id for p in response.context['project_list']]
        assert active_project.id in project_ids
        assert inactive_project.id not in project_ids

    def test_ordering(
        self,
        client,
        superuser,
        multiple_projects,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
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

    def test_context_includes_cost_and_cost_centers(
        self,
        client,
        superuser,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """Test that each project in context has cost and cost_centers."""
        # Create Storage allocation with attributes
        storage_resource = Resource.objects.create(
            name='Test Storage',
            resource_type=storage_resource_type,
            requires_payment=True,
        )
        ResourceAttribute.objects.create(
            resource=storage_resource,
            resource_attribute_type=cost_attribute_type,
            value='100',  # $100 per TB
        )
        allocation = Allocation.objects.create(
            project=project,
            status=allocation_status_active,
            quantity=100,
        )
        allocation.resources.add(storage_resource)
        AllocationAttribute.objects.create(
            allocation=allocation,
            allocation_attribute_type=quota_attribute_type,
            value='5',  # 5 TB
        )

        response = self._get_billing_response(client, superuser)
        assert response.status_code == 200
        assert len(response.context['project_list']) == 1

        for project_obj in response.context['project_list']:
            assert hasattr(project_obj, 'cost')
            assert project_obj.cost.startswith('$')
            # Cost = quota (5 TB) * cost_per_tb (100) = 500
            cost_value = int(project_obj.cost.replace('$', ''))
            assert cost_value == 500
            assert hasattr(project_obj, 'cost_centers')
            assert project_obj.cost_centers == '-'
