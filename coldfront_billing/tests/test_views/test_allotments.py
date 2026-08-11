"""Unit tests for no_cost_quota views: manage, assign, single allotment, and bulk auto-assign."""

from urllib.parse import urlencode
from decimal import Decimal
import pytest
from django.urls import reverse

from coldfront_billing.tests.conftest import add_no_cost_quota_storage_allocation
from coldfront_billing.tests.test_views.common import (
    post_auto_assign_allotments,
    post_create_allotment,
    post_delete_allotment,
)


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
            reverse('no_cost_quota_manage_allotment'),
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
            reverse('no_cost_quota_manage_allotment'),
            data={'allocation_id': allocation.pk, 'amount': '5'},
        )
        assert response.status_code == 302
        assert response.url == reverse('manage_no_cost_quota')

        response = client.post(
            reverse('no_cost_quota_manage_allotment'),
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
        response = post_create_allotment(client, user, no_cost_quota.pk, allocation.pk, 'not-a-number')
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
            amount_tb=Decimal('50.0'),
            units='TB',
            increment_gb=100,  # Increment in GB
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
        response = post_create_allotment(client, user, other_quota.pk, allocation.pk, '5')
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
        response = post_create_allotment(client, user, no_cost_quota.pk, allocation.pk, '5')
        assert response.status_code == 302
        assert response.url == reverse('manage_no_cost_quota')

        allotment = NoCostQuotaAllotment.objects.get(
            no_cost_quota=no_cost_quota,
            allocation=allocation,
        )
        assert allotment.amount_tb == Decimal('5.0')

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
        post_create_allotment(client, user, no_cost_quota.pk, allocation.pk, '1')
        response = post_create_allotment(client, user, no_cost_quota.pk, allocation.pk, '2')
        assert response.status_code == 302

        allotment = NoCostQuotaAllotment.objects.get(
            no_cost_quota=no_cost_quota,
            allocation=allocation,
        )
        assert allotment.amount_tb == Decimal('2.0')
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
            amount_tb=Decimal('1000.0'),  # 1 TB = 1000 GB
            units='GB',
            increment_gb=100,  # Increment in GB
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
        response = post_create_allotment(client, user, gb_quota.pk, allocation.pk, '100')
        assert response.status_code == 302
        assert response.url == reverse('manage_no_cost_quota')

        allotment = NoCostQuotaAllotment.objects.get(
            no_cost_quota=gb_quota,
            allocation=allocation,
        )
        assert allotment.amount_tb == Decimal(100.0)

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
            amount_tb=Decimal('5.0'),
        )
        response = client.post(
            reverse('no_cost_quota_manage_allotment'),
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
            reverse('no_cost_quota_manage_allotment'),
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
            amount_tb=Decimal('5.0'),
        )
        response = post_delete_allotment(client, user, allotment.pk)
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
            amount_tb=Decimal('50.0'),
            units='TB',
            increment_gb=100,  # Increment in GB
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
            amount_tb=Decimal('5.0'),
        )
        response = post_delete_allotment(client, user, allotment.pk)
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
            amount_tb=Decimal('50.0'),
            units='TB',
            increment_gb=100,  # Increment in GB
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
            amount_tb=Decimal('5.0'),
        )
        response = post_delete_allotment(client, superuser, allotment.pk)
        assert response.status_code == 302
        assert response.url == reverse('manage_no_cost_quota')
        assert not NoCostQuotaAllotment.objects.filter(pk=allotment.pk).exists()


@pytest.mark.django_db
@pytest.mark.usefixtures('configure_urls')
class TestAutoAssignAllotmentsView:
    """Test suite for AutoAssignAllotmentsView (bulk allotment create/update)."""

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
        allocation, _ = add_no_cost_quota_storage_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value=no_cost_quota.quota_type,
        )
        body = urlencode(
            [
                ('quota_id', str(no_cost_quota.pk)),
                ('allocation_id', str(allocation.pk)),
                ('amount', '1'),
            ]
        )
        response = client.post(
            reverse('no_cost_quota_auto_allotment'),
            data=body,
            content_type='application/x-www-form-urlencoded',
        )
        assert response.status_code == 302
        assert '/login' in response.url

    def test_missing_quota_id_redirects_to_manage(self, client, user):
        client.force_login(user)
        response = client.post(
            reverse('no_cost_quota_auto_allotment'),
            data='',
            content_type='application/x-www-form-urlencoded',
        )
        assert response.status_code == 302
        assert response.url == reverse('manage_no_cost_quota')

    def test_regular_user_cannot_auto_assign_other_users_quota(
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
        from coldfront_billing.models import NoCostQuota

        other_quota = NoCostQuota.objects.create(
            user=pi_user,
            quota_type='tier_1',
            description='PI quota',
            amount_tb=Decimal('50.0'),
            units='TB',
            increment_gb=100,  # Increment in GB
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
        response = post_auto_assign_allotments(
            client,
            user,
            other_quota.pk,
            [(allocation.pk, '2')],
        )
        assert response.status_code == 302
        assert response.url == reverse('manage_no_cost_quota')

    def test_mismatched_row_counts_redirects_to_assign_with_error(
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
        body = urlencode(
            [
                ('quota_id', str(no_cost_quota.pk)),
                ('allocation_id', str(allocation.pk)),
                ('amount', '1'),
                ('amount', '2'),
            ]
        )
        response = client.post(
            reverse('no_cost_quota_auto_allotment'),
            data=body,
            content_type='application/x-www-form-urlencoded',
        )
        assert response.status_code == 302
        assert f'selected_quota={no_cost_quota.pk}' in response.url

    def test_valid_bulk_post_creates_two_allotments(
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
        from coldfront_billing.models import NoCostQuotaAllotment

        alloc_a, _ = add_no_cost_quota_storage_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value=no_cost_quota.quota_type,
            resource_name='NCQ Bulk A',
        )
        alloc_b, _ = add_no_cost_quota_storage_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value=no_cost_quota.quota_type,
            resource_name='NCQ Bulk B',
        )
        response = post_auto_assign_allotments(
            client,
            user,
            no_cost_quota.pk,
            [(alloc_a.pk, '2'), (alloc_b.pk, '3,0')],
        )
        assert response.status_code == 302
        assert response.url == reverse('manage_no_cost_quota')

        assert NoCostQuotaAllotment.objects.get(no_cost_quota=no_cost_quota, allocation=alloc_a).amount_tb == Decimal('2.0')
        assert NoCostQuotaAllotment.objects.get(no_cost_quota=no_cost_quota, allocation=alloc_b).amount_tb == Decimal('3.0')

    def test_valid_bulk_post_updates_existing_allotments(
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
        NoCostQuotaAllotment.objects.create(
            no_cost_quota=no_cost_quota,
            allocation=allocation,
            amount_tb=Decimal('1.0'),
        )
        response = post_auto_assign_allotments(
            client,
            user,
            no_cost_quota.pk,
            [(allocation.pk, '5')],
        )
        assert response.status_code == 302
        allotment = NoCostQuotaAllotment.objects.get(no_cost_quota=no_cost_quota, allocation=allocation)
        assert allotment.amount_tb == Decimal('5.0')
        assert NoCostQuotaAllotment.objects.filter(no_cost_quota=no_cost_quota, allocation=allocation).count() == 1
