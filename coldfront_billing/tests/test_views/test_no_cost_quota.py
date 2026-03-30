"""Unit tests for no_cost_quota views: manage, assign, single allotment, and bulk auto-assign."""

import pytest
from django.urls import reverse

from coldfront_billing.tests.conftest import add_no_cost_quota_storage_allocation
from coldfront_billing.tests.test_views.common import _get_manage_response, get_assign_response


@pytest.mark.django_db
@pytest.mark.usefixtures('configure_urls')
class TestManageNoCostQuotasView:
    """Test suite for ManageNoCostQuotasView."""

    def test_unauthenticated_user_redirected(self, client):
        """Test that unauthenticated users are redirected to login."""
        response = client.get(reverse('manage_no_cost_quota'))
        assert response.status_code == 302
        assert '/login' in response.url

    def test_superuser_sees_all_quotas(
        self,
        client,
        superuser,
        user,
        no_cost_quota,
    ):
        """Test that superusers see all no-cost quotas."""
        response = _get_manage_response(client, superuser)
        assert response.status_code == 200
        assert 'quota_list' in response.context
        # no_cost_quota belongs to user; superuser should see it
        assert list(response.context['quota_list']) == [no_cost_quota]

    def test_regular_user_sees_only_own_quotas(
        self,
        client,
        user,
        no_cost_quota,
    ):
        """Test that regular users see only their own quotas."""
        response = _get_manage_response(client, user)
        assert response.status_code == 200
        assert list(response.context['quota_list']) == [no_cost_quota]

    def test_regular_user_does_not_see_other_users_quotas(
        self,
        client,
        user,
        pi_user,
    ):
        """Test that regular users do not see quotas owned by other users."""
        from coldfront_billing.models import NoCostQuota

        other_quota = NoCostQuota.objects.create(
            user=pi_user,
            quota_type='tier_1',
            description='PI quota',
            amount=50.0,
            units='TB',
            minimum_increment=0.1,
        )
        response = _get_manage_response(client, user)
        assert response.status_code == 200
        assert list(response.context['quota_list']) == []
        assert other_quota not in response.context['quota_list']

    def test_manage_page_shows_quota_in_gb(
        self,
        client,
        user,
    ):
        """Test that manage page displays NoCostQuota with GB units."""
        from coldfront_billing.models import NoCostQuota

        gb_quota = NoCostQuota.objects.create(
            user=user,
            quota_type='tier_2',
            description='Tier 2 storage in GB',
            amount=1000.0,
            units='GB',
            minimum_increment=100,
        )
        response = _get_manage_response(client, user)
        assert response.status_code == 200
        assert gb_quota in response.context['quota_list']
        assert gb_quota.units == 'GB'


@pytest.mark.django_db
@pytest.mark.usefixtures('configure_urls')
class TestAssignNoCostQuotasView:
    """Test suite for AssignNoCostQuotasView."""

    def test_unauthenticated_user_redirected(self, client, no_cost_quota):
        """Test that unauthenticated users are redirected to login."""
        response = client.get(f'{reverse("assign_no_cost_quota")}?selected_quota={no_cost_quota.pk}')
        assert response.status_code == 302
        assert '/login' in response.url

    def test_missing_selected_quota_redirects_with_error(self, client, user):
        """Test that missing selected_quota redirects to manage with error."""
        response = get_assign_response(client, user, '')
        assert response.status_code == 302
        assert response.url == reverse('manage_no_cost_quota')

    def test_nonexistent_quota_returns_404(self, client, user):
        """Test that nonexistent quota returns 404."""
        response = get_assign_response(client, user, 99999)
        assert response.status_code == 404

    def test_regular_user_cannot_assign_other_users_quota(
        self,
        client,
        user,
        pi_user,
    ):
        """Test that regular user cannot assign quota owned by another user."""
        from coldfront_billing.models import NoCostQuota

        other_quota = NoCostQuota.objects.create(
            user=pi_user,
            quota_type='tier_1',
            description='PI quota',
            amount=50.0,
            units='TB',
            minimum_increment=0.1,
        )
        response = get_assign_response(client, user, other_quota.pk)
        assert response.status_code == 302
        assert response.url == reverse('manage_no_cost_quota')

    def test_superuser_can_assign_any_quota(
        self,
        client,
        superuser,
        user,
        no_cost_quota,
        project_with_billing_user,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        """Test that superuser can access assign page for any quota."""
        add_no_cost_quota_storage_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value=no_cost_quota.quota_type,
        )
        response = get_assign_response(client, superuser, no_cost_quota.pk)
        assert response.status_code == 200
        assert response.context['quota'] == no_cost_quota
        assert 'allocations' in response.context

    def test_owner_can_assign_own_quota(
        self,
        client,
        user,
        no_cost_quota,
        project_with_billing_user,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        """Test that quota owner can access assign page for their quota."""
        add_no_cost_quota_storage_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value=no_cost_quota.quota_type,
        )
        response = get_assign_response(client, user, no_cost_quota.pk)
        assert response.status_code == 200
        assert response.context['quota'] == no_cost_quota

    def test_assign_page_shows_eligible_allocations(
        self,
        client,
        user,
        no_cost_quota,
        project_with_billing_user,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        """Test that assign page shows allocations eligible for the quota."""
        allocation, _ = add_no_cost_quota_storage_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value=no_cost_quota.quota_type,
        )
        response = get_assign_response(client, user, no_cost_quota.pk)
        assert response.status_code == 200
        allocations_data = response.context['allocations']
        assert len(allocations_data) == 1
        assert allocations_data[0]['allocation'] == allocation
        assert 'max_possible' in allocations_data[0]
        assert 'existing_amount' in allocations_data[0]
        assert 'allotment_id' in allocations_data[0]

    def test_assign_page_shows_allotment_id_when_allotment_exists(
        self,
        client,
        user,
        no_cost_quota,
        project_with_billing_user,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        """Test that assign page shows allotment_id for allocation with existing allotment."""
        from coldfront_billing.models import NoCostQuotaAllotment

        allocation, _ = add_no_cost_quota_storage_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value=no_cost_quota.quota_type,
        )
        allotment = NoCostQuotaAllotment.objects.create(
            no_cost_quota=no_cost_quota,
            allocation=allocation,
            amount=5.0,
        )
        response = get_assign_response(client, user, no_cost_quota.pk)
        assert response.status_code == 200
        allocations_data = response.context['allocations']
        assert len(allocations_data) == 1
        assert allocations_data[0]['allotment_id'] == allotment.pk

    def test_assign_page_shows_empty_allotment_id_when_no_allotment(
        self,
        client,
        user,
        no_cost_quota,
        project_with_billing_user,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        """Test that assign page shows empty allotment_id for allocation without allotment."""
        allocation, _ = add_no_cost_quota_storage_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value=no_cost_quota.quota_type,
        )
        response = get_assign_response(client, user, no_cost_quota.pk)
        assert response.status_code == 200
        allocations_data = response.context['allocations']
        assert len(allocations_data) == 1
        assert allocations_data[0]['allotment_id'] == ''
