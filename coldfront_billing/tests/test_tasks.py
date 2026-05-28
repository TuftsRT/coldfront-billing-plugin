"""Tests for scheduled billing report task."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from django_q.models import Schedule

from coldfront_billing.constants import BILLING_SCHEDULE_NAME
from coldfront_billing.models import BillingScheduleHistory, BillingScheduleSettings
from coldfront_billing.tasks import run_scheduled_billing_report


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

    @patch('coldfront_billing.reports.send_billing_report_email')
    @patch('coldfront_billing.reports.auto_assign_quota')
    def test_success_records_history(self, mock_auto_assign, mock_send_mail):
        mock_send_mail.return_value = {'success': True, 'message': 'Email with attachment sent!'}
        _settings()
        result = run_scheduled_billing_report()
        assert result['success'] is True
        mock_auto_assign.assert_not_called()
        history = BillingScheduleHistory.objects.get()
        assert history.status == BillingScheduleHistory.Status.SUCCESS
        assert history.details == ''

    @patch('coldfront_billing.reports.send_billing_report_email')
    @patch('coldfront_billing.reports.auto_assign_quota')
    def test_auto_assign_failure_records_history(self, mock_auto_assign, mock_send_mail):
        mock_auto_assign.side_effect = RuntimeError('assign failed')
        _settings(autoassign_no_cost_quota=True)
        result = run_scheduled_billing_report()
        assert result == {'success': False, 'message': 'Auto-assign failed: assign failed'}
        mock_send_mail.assert_not_called()
        history = BillingScheduleHistory.objects.get()
        assert history.status == BillingScheduleHistory.Status.FAILED_AUTOASSIGN
        assert 'assign failed' in history.details

    @patch('coldfront_billing.reports.send_billing_report_email')
    @patch('coldfront_billing.reports.auto_assign_quota')
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

    @patch('coldfront_billing.reports.send_billing_report_email')
    @patch('coldfront_billing.reports.auto_assign_quota')
    def test_mail_failure_defaults_to_failed_mail(self, mock_auto_assign, mock_send_mail):
        mock_send_mail.return_value = {'success': False, 'message': 'smtp down'}
        _settings()
        run_scheduled_billing_report()
        history = BillingScheduleHistory.objects.get()
        assert history.status == BillingScheduleHistory.Status.FAILED_MAIL
        assert history.details == 'smtp down'
