"""Tests for reports.nocostquota.get_oversubscribed_no_cost_quotas."""

from decimal import Decimal

import pytest

from coldfront.core.allocation.models import (
    AllocationAttribute,
    AllocationAttributeType,
)
from coldfront.core.allocation.models import (
    AttributeType as AllocationAttributeTypeBase,
)

from coldfront_billing.models import NoCostQuotaAllotment
from coldfront_billing.reports.nocostquota import get_oversubscribed_no_cost_quotas
from coldfront_billing.tests.conftest import add_no_cost_quota_storage_allocation, add_storage_allocation_to_project


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

    def test_quota_is_converted_from_bytes_exactly(
        self,
        no_cost_quota,
        project_with_billing_user,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
        no_cost_quota_type_attribute_type,
    ):
        """
        155,000,000,000 bytes is 0.155 TB, which rounds to 0.16 and so covers a 0.16 TB allotment.
        Divided as floats it is 0.15499999..., which rounds to 0.15 and flags the allocation.
        """
        allocation, _ = add_no_cost_quota_storage_allocation(
            project_with_billing_user,
            storage_resource_type,
            allocation_status_active,
            cost_attribute_type,
            quota_attribute_type,
            no_cost_quota_type_attribute_type,
            quota_type_value=no_cost_quota.quota_type,
        )
        text_attr_type, _ = AllocationAttributeTypeBase.objects.get_or_create(name='Text')
        reported_quota_type, _ = AllocationAttributeType.objects.get_or_create(
            name='reported_quota_bytes',
            defaults={'attribute_type': text_attr_type},
        )
        AllocationAttribute.objects.create(
            allocation=allocation,
            allocation_attribute_type=reported_quota_type,
            value='155000000000',
        )
        NoCostQuotaAllotment.objects.create(
            no_cost_quota=no_cost_quota, allocation=allocation, amount_tb=Decimal('0.16')
        )

        assert get_oversubscribed_no_cost_quotas() == []
