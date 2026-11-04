"""Unit tests for coldfront_billing.allotments."""

from decimal import Decimal

import pytest

from coldfront_billing.allotments import create_or_update_allotment, create_update_allotment
from coldfront_billing.models import NoCostQuotaAllotment, NoCostQuotaAllotmentFailure
from coldfront_billing.tests.conftest import add_no_cost_quota_storage_allocation


@pytest.mark.django_db
class TestCreateUpdateAllotment:
    def test_creates_new_allotment(
        self,
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
        result = create_update_allotment(allocation, Decimal('2.0'), no_cost_quota)
        assert result == 'Assigned'
        assert NoCostQuotaAllotment.objects.filter(allocation=allocation, amount_tb=Decimal('2.0')).exists()

    def test_updates_existing_allotment(
        self,
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
        NoCostQuotaAllotment.objects.create(
            no_cost_quota=no_cost_quota, allocation=allocation, amount_tb=Decimal('1.0')
        )
        result = create_update_allotment(allocation, Decimal('3.0'), no_cost_quota)
        assert result == 'Updated'
        assert NoCostQuotaAllotment.objects.get(allocation=allocation).amount_tb == Decimal('3.0')

    def test_append_increments_amount(
        self,
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
        NoCostQuotaAllotment.objects.create(
            no_cost_quota=no_cost_quota, allocation=allocation, amount_tb=Decimal('1.0')
        )
        create_update_allotment(allocation, Decimal('2.0'), no_cost_quota, append=True)
        assert NoCostQuotaAllotment.objects.get(allocation=allocation).amount_tb == Decimal('3.0')

    def test_validation_error_wrapped(
        self,
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
        with pytest.raises(Exception, match='Could not save allotment'):
            create_update_allotment(allocation, Decimal('-1.0'), no_cost_quota)

    def test_invalid_new_allotment_is_not_saved(
        self,
        user,
        no_cost_quota,
        project_with_billing_user,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        """Validation runs before the insert, so a rejected amount leaves no allotment behind."""
        allocation, _ = add_no_cost_quota_storage_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value=no_cost_quota.quota_type,
        )
        with pytest.raises(Exception, match='multiple of increment'):
            create_update_allotment(allocation, Decimal('1.005'), no_cost_quota)
        assert not NoCostQuotaAllotment.objects.filter(allocation=allocation).exists()

    def test_create_or_update_allotment_by_id(
        self,
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
        assert create_or_update_allotment(allocation.pk, Decimal('1.0'), no_cost_quota) == 'Assigned'

    def test_saving_an_allotment_resolves_earlier_failures_from_that_quota(
        self,
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
        from_this_quota = NoCostQuotaAllotmentFailure.objects.create(
            allocation=allocation, no_cost_quota=no_cost_quota, message='earlier'
        )
        unknown_quota = NoCostQuotaAllotmentFailure.objects.create(allocation=allocation, message='bad id')

        create_update_allotment(allocation, Decimal('2.0'), no_cost_quota)

        from_this_quota.refresh_from_db()
        unknown_quota.refresh_from_db()
        assert from_this_quota.resolved_at is not None
        assert from_this_quota.resolved_by is None
        assert unknown_quota.resolved_at is None

    def test_a_rejected_allotment_resolves_nothing(
        self,
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
        failure = NoCostQuotaAllotmentFailure.objects.create(
            allocation=allocation, no_cost_quota=no_cost_quota, message='earlier'
        )

        with pytest.raises(Exception, match='Could not save allotment'):
            create_update_allotment(allocation, Decimal('1.005'), no_cost_quota)

        failure.refresh_from_db()
        assert failure.resolved_at is None
