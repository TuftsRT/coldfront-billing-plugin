"""Unit tests for coldfront_billing.allotments."""

from decimal import Decimal

import pytest

from coldfront_billing.allotments import create_or_update_allotment, create_update_allotment
from coldfront_billing.models import NoCostQuotaAllotment
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
            no_cost_quota=no_cost_quota,
            allocation=allocation,
            amount_tb=Decimal('1.0')
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
            no_cost_quota=no_cost_quota,
            allocation=allocation,
            amount_tb=Decimal('1.0')
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
