"""Tests for reports.quota.auto_assign_quota."""

import pytest

from coldfront_billing.models import NoCostQuota, NoCostQuotaAllotment
from coldfront_billing.reports.quota import auto_assign_quota
from coldfront_billing.tests.conftest import add_no_cost_quota_storage_allocation


@pytest.mark.django_db
class TestAutoAssignQuota:
    def test_skipped_when_no_eligible_quotas(self, storage_resource_type):
        status, message = auto_assign_quota()
        assert status == 'skipped'
        assert 'nothing to do' in message.lower()

    def test_assigns_allotments_for_pi_with_remaining_quota(
        self,
        pi_user,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        quota = NoCostQuota.objects.create(
            user=pi_user,
            quota_type='tier_1',
            description='PI tier',
            amount_tb=20.0,
            units='TB',
            increment_gb=1000,
        )
        allocation, _ = add_no_cost_quota_storage_allocation(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value=quota.quota_type,
            quota_value='10',
        )
        status, message = auto_assign_quota()
        assert status == 'ok'
        assert '1 quota' in message
        assert NoCostQuotaAllotment.objects.filter(
            no_cost_quota=quota,
            allocation=allocation,
        ).exists()
