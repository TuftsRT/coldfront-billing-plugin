"""Tests for scheduled billing report task."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from django_q.models import Schedule

from coldfront.core.allocation.models import (
    AllocationAttribute,
    AllocationAttributeType,
)
from coldfront.core.allocation.models import (
    AttributeType as AllocationAttributeTypeBase,
)

from coldfront_billing.constants import BILLING_SCHEDULE_NAME
from coldfront_billing.models import BillingScheduleHistory, BillingScheduleSettings, NoCostQuota, NoCostQuotaAllotment
from coldfront_billing.tasks import fix_oversubscribed_no_cost_quotas, run_scheduled_billing_report
from coldfront_billing.tests.conftest import add_storage_allocation_to_project


def _settings(**overrides):
    BillingScheduleSettings.objects.all().delete()
    defaults = {
        'scheduling_enabled': True,
        'start_date': timezone.localdate(),
        'notification_email': 'billing@test.local',
        'autoassign_no_cost_quota': False,
    }
    defaults.update(overrides)
    return BillingScheduleSettings.objects.create(**defaults)


@pytest.mark.django_db
class TestRunScheduledBillingReport:
    def test_no_settings_returns_failure(self):
        BillingScheduleSettings.objects.all().delete()
        result = run_scheduled_billing_report()
        assert result == {'success': False, 'message': 'No billing settings found'}

    def test_expired_schedule_deletes_django_q_schedule(self):
        past = timezone.localdate() - timedelta(days=1)
        _settings(end_date=past)
        Schedule.objects.create(name=BILLING_SCHEDULE_NAME, func='x', schedule_type=Schedule.MONTHLY)
        result = run_scheduled_billing_report()
        assert result == {'success': False, 'message': 'Schedule expired'}
        assert not Schedule.objects.filter(name=BILLING_SCHEDULE_NAME).exists()

    @patch('coldfront_billing.tasks.send_billing_report_email')
    @patch('coldfront_billing.tasks.auto_assign_quota')
    def test_success_records_history(self, mock_auto_assign, mock_send_mail):
        mock_send_mail.return_value = {'success': True, 'message': 'Email with attachment sent!'}
        _settings()
        result = run_scheduled_billing_report()
        assert result['success'] is True
        mock_auto_assign.assert_not_called()
        history = BillingScheduleHistory.objects.get()
        assert history.status == BillingScheduleHistory.Status.SUCCESS
        assert history.details == ''

    @patch('coldfront_billing.tasks.send_billing_report_email')
    @patch('coldfront_billing.tasks.auto_assign_quota')
    def test_auto_assign_failure_records_history(self, mock_auto_assign, mock_send_mail):
        mock_auto_assign.side_effect = RuntimeError('assign failed')
        _settings(autoassign_no_cost_quota=True)
        result = run_scheduled_billing_report()
        assert result == {'success': False, 'message': 'Auto-assign failed: assign failed'}
        mock_send_mail.assert_not_called()
        history = BillingScheduleHistory.objects.get()
        assert history.status == BillingScheduleHistory.Status.FAILED_AUTOASSIGN
        assert 'assign failed' in history.details

    @patch('coldfront_billing.tasks.send_billing_report_email')
    @patch('coldfront_billing.tasks.auto_assign_quota')
    def test_mail_failure_uses_history_status_from_result(self, mock_auto_assign, mock_send_mail):
        mock_send_mail.return_value = {
            'success': False,
            'message': 'No storage resource found',
            'history_status': BillingScheduleHistory.Status.FAILED_REPORT,
        }
        _settings()
        result = run_scheduled_billing_report()
        assert result['success'] is False
        history = BillingScheduleHistory.objects.get()
        assert history.status == BillingScheduleHistory.Status.FAILED_REPORT
        assert history.details == 'No storage resource found'

    @patch('coldfront_billing.tasks.send_billing_report_email')
    @patch('coldfront_billing.tasks.auto_assign_quota')
    def test_mail_failure_defaults_to_failed_mail(self, mock_auto_assign, mock_send_mail):
        mock_send_mail.return_value = {'success': False, 'message': 'smtp down'}
        _settings()
        run_scheduled_billing_report()
        history = BillingScheduleHistory.objects.get()
        assert history.status == BillingScheduleHistory.Status.FAILED_MAIL
        assert history.details == 'smtp down'


@pytest.mark.django_db
class TestFixOversubscribedNoCostQuotas:
    def test_quantization_never_drives_allotment_amount_negative(
        self,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """
        Trigger: get_oversubscribed_no_cost_quotas compares an exact allotment
        total (sum of amount_tb, 0.015 TB below) against reported_quota_bytes
        converted to TB via `Decimal(int(quota)) / 10**12`. With
        reported_quota_bytes = 0 that is 0, so this fires because 0.015 TB is
        more than the allocation's reported 0 TB quota.

        Reduction: reduce_allotments_evenly separately recomputes an exact
        reduction_value from amount_tb and the allocation's quota_in_terabyte
        attribute.
        With quota_in_terabyte = -0.005, reduction_value ~= 0.02 - more than the
        true 0.015 total.

        Either way, each reduction is capped at the allotment's own amount_tb,
        so neither allotment should ever end up negative even though more was
        requested than actually exists across both of them.
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
            value='0',
        )
        AllocationAttribute.objects.create(
            allocation=allocation,
            allocation_attribute_type=quota_attribute_type,
            value='-0.005',
        )

        quota_a = NoCostQuota.objects.create(
            user=project.pi,
            quota_type='tier_1',
            description='a',
            amount_tb=Decimal('100'),
            units='TB',
            increment_gb=1,
        )
        quota_b = NoCostQuota.objects.create(
            user=project.pi,
            quota_type='tier_2',
            description='b',
            amount_tb=Decimal('100'),
            units='TB',
            increment_gb=1,
        )
        allotment_a = NoCostQuotaAllotment.objects.create(
            no_cost_quota=quota_a, allocation=allocation, amount_tb=Decimal('0.010')
        )
        allotment_b = NoCostQuotaAllotment.objects.create(
            no_cost_quota=quota_b, allocation=allocation, amount_tb=Decimal('0.005')
        )

        fix_oversubscribed_no_cost_quotas()

        assert not NoCostQuotaAllotment.objects.filter(amount_tb__lt=0).exists()
        # ~0.02 requested against a true total of 0.015: both allotments are
        # fully drained to exactly zero (and deleted) rather than driven negative.
        assert not NoCostQuotaAllotment.objects.filter(pk__in=[allotment_a.pk, allotment_b.pk]).exists()

    def test_deletes_allotments_reduced_to_zero(
        self,
        project,
        storage_resource_type,
        allocation_status_active,
        cost_attribute_type,
        quota_attribute_type,
    ):
        """
        quota_in_terabyte = 0.125 TB against allotments totaling 0.375 TB
        means reduce_allotments_evenly needs to remove 0.250 TB, split evenly: 0.125 TB
        from each. That exactly drains allotment_a (0.125 TB) to zero, which
        fix_oversubscribed_no_cost_quotas should delete,
        while allotment_b (0.250 TB) is left with a nonzero 0.125 TB and should be kept.
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
            value='0',
        )
        AllocationAttribute.objects.create(
            allocation=allocation,
            allocation_attribute_type=quota_attribute_type,
            value='0.125',
        )

        quota_a = NoCostQuota.objects.create(
            user=project.pi,
            quota_type='tier_1',
            description='a',
            amount_tb=Decimal('100'),
            units='TB',
            increment_gb=1,
        )
        quota_b = NoCostQuota.objects.create(
            user=project.pi,
            quota_type='tier_2',
            description='b',
            amount_tb=Decimal('100'),
            units='TB',
            increment_gb=1,
        )
        allotment_a = NoCostQuotaAllotment.objects.create(
            no_cost_quota=quota_a, allocation=allocation, amount_tb=Decimal('0.125')
        )
        allotment_b = NoCostQuotaAllotment.objects.create(
            no_cost_quota=quota_b, allocation=allocation, amount_tb=Decimal('0.250')
        )

        fix_oversubscribed_no_cost_quotas()

        assert not NoCostQuotaAllotment.objects.filter(pk=allotment_a.pk).exists()
        allotment_b.refresh_from_db()
        assert allotment_b.amount_tb == Decimal('0.125')
