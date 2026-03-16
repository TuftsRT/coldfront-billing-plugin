"""Unit tests for no_cost_quota views: ManageNoCostQuotasView, AssignNoCostQuotasView, NoCostQuotaAllotmentView."""

import pytest
from django.urls import reverse

from .conftest import add_no_cost_quota_storage_allocation


def _post_delete_allotment(client, user, allotment_id):
    """Helper to POST delete allotment."""
    client.force_login(user)
    return client.post(
        reverse('no_cost_quota_allotment'),
        data={
            'action': 'delete',
            'allotment_id': allotment_id,
        },
    )


def _get_manage_response(client, user):
    """Helper to GET the manage no cost quota page."""
    client.force_login(user)
    return client.get(reverse('manage_no_cost_quota'))


def _get_assign_response(client, user, selected_quota):
    """Helper to GET the assign no cost quota page."""
    client.force_login(user)
    url = f"{reverse('assign_no_cost_quota')}?selected_quota={selected_quota}"
    return client.get(url)


def _post_create_allotment(client, user, quota_id, allocation_id, amount):
    """Helper to POST create allotment."""
    client.force_login(user)
    return client.post(
        reverse('no_cost_quota_allotment'),
        data={
            'quota_id': quota_id,
            'allocation_id': allocation_id,
            'amount': amount,
        },
    )


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
        response = client.get(f"{reverse('assign_no_cost_quota')}?selected_quota={no_cost_quota.pk}")
        assert response.status_code == 302
        assert '/login' in response.url

    def test_missing_selected_quota_redirects_with_error(self, client, user):
        """Test that missing selected_quota redirects to manage with error."""
        response = _get_assign_response(client, user, '')
        assert response.status_code == 302
        assert response.url == reverse('manage_no_cost_quota')

    def test_nonexistent_quota_returns_404(self, client, user):
        """Test that nonexistent quota returns 404."""
        response = _get_assign_response(client, user, 99999)
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
        response = _get_assign_response(client, user, other_quota.pk)
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
        response = _get_assign_response(client, superuser, no_cost_quota.pk)
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
        response = _get_assign_response(client, user, no_cost_quota.pk)
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
        response = _get_assign_response(client, user, no_cost_quota.pk)
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
        response = _get_assign_response(client, user, no_cost_quota.pk)
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
        response = _get_assign_response(client, user, no_cost_quota.pk)
        assert response.status_code == 200
        allocations_data = response.context['allocations']
        assert len(allocations_data) == 1
        assert allocations_data[0]['allotment_id'] == ''


@pytest.mark.django_db
@pytest.mark.usefixtures('configure_urls')
class TestNoCostQuotaAllotmentView:
    """Test suite for NoCostQuotaAllotmentView."""

    def test_unauthenticated_user_redirected(
        self,
        client,
        no_cost_quota,
        project_with_billing_user,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        """Test that unauthenticated users are redirected to login."""
        allocation, _ = add_no_cost_quota_storage_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value=no_cost_quota.quota_type,
        )
        response = client.post(
            reverse('no_cost_quota_allotment'),
            data={
                'quota_id': no_cost_quota.pk,
                'allocation_id': allocation.pk,
                'amount': '5',
            },
        )
        assert response.status_code == 302
        assert '/login' in response.url

    def test_missing_quota_or_allocation_redirects_with_error(
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
        """Test that missing quota_id or allocation_id redirects with error."""
        allocation, _ = add_no_cost_quota_storage_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value=no_cost_quota.quota_type,
        )
        client.force_login(user)

        response = client.post(
            reverse('no_cost_quota_allotment'),
            data={'allocation_id': allocation.pk, 'amount': '5'},
        )
        assert response.status_code == 302
        assert response.url == reverse('manage_no_cost_quota')

        response = client.post(
            reverse('no_cost_quota_allotment'),
            data={'quota_id': no_cost_quota.pk, 'amount': '5'},
        )
        assert response.status_code == 302
        assert response.url == reverse('manage_no_cost_quota')

    def test_invalid_amount_redirects_with_error(
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
        """Test that invalid amount redirects to assign page with error."""
        allocation, _ = add_no_cost_quota_storage_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value=no_cost_quota.quota_type,
        )
        response = _post_create_allotment(client, user, no_cost_quota.pk, allocation.pk, 'not-a-number')
        assert response.status_code == 302
        assert f'selected_quota={no_cost_quota.pk}' in response.url

    def test_regular_user_cannot_create_allotment_for_other_users_quota(
        self,
        client,
        user,
        pi_user,
        project_with_billing_user,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        """Test that regular user cannot create allotment for another user's quota."""
        from coldfront_billing.models import NoCostQuota

        other_quota = NoCostQuota.objects.create(
            user=pi_user,
            quota_type='tier_1',
            description='PI quota',
            amount=50.0,
            units='TB',
            minimum_increment=0.1,
        )
        allocation, _ = add_no_cost_quota_storage_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value=other_quota.quota_type,
        )
        response = _post_create_allotment(client, user, other_quota.pk, allocation.pk, '5')
        assert response.status_code == 302
        assert response.url == reverse('manage_no_cost_quota')

    def test_valid_post_creates_allotment(
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
        """Test that valid POST creates NoCostQuotaAllotment and redirects."""
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
        response = _post_create_allotment(client, user, no_cost_quota.pk, allocation.pk, '5')
        assert response.status_code == 302
        assert response.url == reverse('manage_no_cost_quota')

        allotment = NoCostQuotaAllotment.objects.get(
            no_cost_quota=no_cost_quota,
            allocation=allocation,
        )
        assert allotment.amount == 5.0

    def test_valid_post_updates_existing_allotment(
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
        """Test that valid POST updates existing allotment amount."""
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
        _post_create_allotment(client, user, no_cost_quota.pk, allocation.pk, '1')
        response = _post_create_allotment(client, user, no_cost_quota.pk, allocation.pk, '2')
        assert response.status_code == 302

        allotment = NoCostQuotaAllotment.objects.get(
            no_cost_quota=no_cost_quota,
            allocation=allocation,
        )
        assert allotment.amount == 2.0
        assert (
            NoCostQuotaAllotment.objects.filter(
                no_cost_quota=no_cost_quota,
                allocation=allocation,
            ).count()
            == 1
        )

    def test_valid_post_creates_allotment_with_gb_quota(
        self,
        client,
        user,
        project_with_billing_user,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        """Test that valid POST creates allotment when NoCostQuota uses GB units."""
        from coldfront_billing.models import NoCostQuota, NoCostQuotaAllotment

        gb_quota = NoCostQuota.objects.create(
            user=user,
            quota_type='tier_2',
            description='Tier 2 storage in GB',
            amount=1000.0,
            units='GB',
            minimum_increment=100,
        )
        allocation, _ = add_no_cost_quota_storage_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value=gb_quota.quota_type,
            quota_value='1000',  # 1000 TB allocation for GB allotment validation
        )
        response = _post_create_allotment(client, user, gb_quota.pk, allocation.pk, '100')
        assert response.status_code == 302
        assert response.url == reverse('manage_no_cost_quota')

        allotment = NoCostQuotaAllotment.objects.get(
            no_cost_quota=gb_quota,
            allocation=allocation,
        )
        assert allotment.amount == 100.0

    def test_unauthenticated_user_cannot_delete_allotment(
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
        """Test that unauthenticated users are redirected to login when deleting allotment."""
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
        response = client.post(
            reverse('no_cost_quota_allotment'),
            data={'action': 'delete', 'allotment_id': allotment.pk},
        )
        assert response.status_code == 302
        assert '/login' in response.url
        assert NoCostQuotaAllotment.objects.filter(pk=allotment.pk).exists()

    def test_missing_allotment_id_redirects_with_error(
        self,
        client,
        user,
    ):
        """Test that delete action without allotment_id redirects to manage with error."""
        client.force_login(user)
        response = client.post(
            reverse('no_cost_quota_allotment'),
            data={'action': 'delete'},
        )
        assert response.status_code == 302
        assert response.url == reverse('manage_no_cost_quota')

    def test_valid_delete_removes_allotment(
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
        """Test that valid delete POST removes allotment and redirects."""
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
        response = _post_delete_allotment(client, user, allotment.pk)
        assert response.status_code == 302
        assert response.url == reverse('manage_no_cost_quota')
        assert not NoCostQuotaAllotment.objects.filter(pk=allotment.pk).exists()

    def test_regular_user_cannot_delete_other_users_allotment(
        self,
        client,
        user,
        pi_user,
        project_with_billing_user,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        """Test that regular user cannot delete allotment owned by another user."""
        from coldfront_billing.models import NoCostQuota, NoCostQuotaAllotment

        other_quota = NoCostQuota.objects.create(
            user=pi_user,
            quota_type='tier_1',
            description='PI quota',
            amount=50.0,
            units='TB',
            minimum_increment=0.1,
        )
        allocation, _ = add_no_cost_quota_storage_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value=other_quota.quota_type,
        )
        allotment = NoCostQuotaAllotment.objects.create(
            no_cost_quota=other_quota,
            allocation=allocation,
            amount=5.0,
        )
        response = _post_delete_allotment(client, user, allotment.pk)
        assert response.status_code == 302
        assert response.url == reverse('manage_no_cost_quota')
        assert NoCostQuotaAllotment.objects.filter(pk=allotment.pk).exists()

    def test_superuser_can_delete_any_allotment(
        self,
        client,
        superuser,
        pi_user,
        project_with_billing_user,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        """Test that superuser can delete allotment owned by any user."""
        from coldfront_billing.models import NoCostQuota, NoCostQuotaAllotment

        pi_quota = NoCostQuota.objects.create(
            user=pi_user,
            quota_type='tier_1',
            description='PI quota',
            amount=50.0,
            units='TB',
            minimum_increment=0.1,
        )
        allocation, _ = add_no_cost_quota_storage_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value=pi_quota.quota_type,
        )
        allotment = NoCostQuotaAllotment.objects.create(
            no_cost_quota=pi_quota,
            allocation=allocation,
            amount=5.0,
        )
        response = _post_delete_allotment(client, superuser, allotment.pk)
        assert response.status_code == 302
        assert response.url == reverse('manage_no_cost_quota')
        assert not NoCostQuotaAllotment.objects.filter(pk=allotment.pk).exists()
