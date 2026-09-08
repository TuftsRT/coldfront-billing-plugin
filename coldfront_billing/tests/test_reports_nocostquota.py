"""Tests for reports.nocostquota.get_oversubscribed_no_cost_quotas."""

import pytest

from coldfront.core.allocation.models import (
    AllocationAttribute,
    AllocationAttributeType,
)
from coldfront.core.allocation.models import (
    AttributeType as AllocationAttributeTypeBase,
)

from coldfront_billing.reports.nocostquota import get_oversubscribed_no_cost_quotas
from coldfront_billing.tests.conftest import add_storage_allocation_to_project


@pytest.mark.django_db
class TestGetOversubscribedNoCostQuotas:
    def test_allocation_without_allotments_is_not_flagged(
        self,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """
        An allocation can require payment and report a quota without ever having
        had a NoCostQuotaAllotment created for it. NoCostQuotaAllotment.objects
        .filter(allocation=allocation) is then empty, so
        sum(allot.amount_tb for allot in ncq_allotment) falls back to the plain
        int 0 rather than a Decimal. get_oversubscribed_no_cost_quotas should
        handle that without raising, and shouldn't flag the allocation.
        """
        allocation, _ = add_storage_allocation_to_project(
            project,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            with_quota=False,
        )

        text_attr_type, _ = AllocationAttributeTypeBase.objects.get_or_create(name='Text')
        reported_quota_type, _ = AllocationAttributeType.objects.get_or_create(
            name='reported_quota_bytes',
            defaults={'attribute_type': text_attr_type},
        )
        AllocationAttribute.objects.create(
            allocation=allocation,
            allocation_attribute_type=reported_quota_type,
            value='5000000000000',  # 5 TB
        )

        assert get_oversubscribed_no_cost_quotas() == []
