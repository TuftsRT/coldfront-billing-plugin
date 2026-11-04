"""Unit tests for coldfront_billing.models.no_cost_quota."""

from decimal import Decimal

import pytest

from coldfront_billing.models import NoCostQuotaAllotment
from coldfront_billing.models.no_cost_quota import quota_with_remaining
from coldfront_billing.tests.conftest import add_no_cost_quota_storage_allocation


@pytest.mark.django_db
class TestQuotaWithRemaining:
    def test_query_sends_no_float_parameters(self):
        """
        On Postgres a float parameter makes COALESCE(SUM(numeric), 0.0) double precision, and
        Django reads that back as Decimal(float), e.g. 99.9 -> 99.900000000000005684...
        SQLite doesn't show the difference, so check what the query sends instead.
        """
        _, params = quota_with_remaining.all().query.sql_with_params()
        assert not [param for param in params if isinstance(param, float)]

    def test_remaining_is_exact(
        self,
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
            no_cost_quota=no_cost_quota, allocation=allocation, amount_tb=Decimal('0.1')
        )

        quota = quota_with_remaining.get(pk=no_cost_quota.pk)

        assert quota.used == Decimal('0.1')
        assert quota.remaining == Decimal('99.9')
        assert quota.remaining_normalized == Decimal('99.9')
