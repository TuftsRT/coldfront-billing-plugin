"""Direct tests for reports.mail.send_billing_report_email edge cases."""

from unittest.mock import MagicMock, patch

import pytest

from coldfront_billing.models import BillingScheduleHistory
from coldfront_billing.reports.mail import send_billing_report_email
from coldfront_billing.utils import NoStorageException


@pytest.mark.django_db
class TestSendBillingReportEmail:
    def test_no_settings_object(self):
        result = send_billing_report_email(None)
        assert result['success'] is False
        assert result['history_status'] == BillingScheduleHistory.Status.FAILED_MAIL

    def test_empty_notification_email(self, db):
        from django.utils import timezone

        from coldfront_billing.models import BillingScheduleSettings

        settings = BillingScheduleSettings.objects.create(
            scheduling_enabled=False,
            start_date=timezone.localdate(),
            notification_email='',
        )
        result = send_billing_report_email(settings)
        assert result['message'] == 'No email address configured'

    @patch(
        'coldfront_billing.reports.mail.validate_emails',
        return_value=(['billing@tufts.com'], []),
    )
    @patch('coldfront_billing.reports.mail.create_csv_report', side_effect=NoStorageException())
    def test_no_storage_exception(self, _mock_csv, _mock_validate, db):
        from django.utils import timezone

        from coldfront_billing.models import BillingScheduleSettings

        settings = BillingScheduleSettings.objects.create(
            scheduling_enabled=False,
            start_date=timezone.localdate(),
            notification_email='billing@tufts.com',
        )
        result = send_billing_report_email(settings)
        assert result['history_status'] == BillingScheduleHistory.Status.FAILED_REPORT

    @patch(
        'coldfront_billing.reports.mail.validate_emails',
        return_value=(['billing@tufts.com'], []),
    )
    @patch('coldfront_billing.reports.mail.EmailMessage')
    @patch('coldfront_billing.reports.mail.create_csv_report', return_value=('r.csv', 'data'))
    def test_send_failure(self, _mock_csv, mock_email_class, _mock_validate, db):
        from django.utils import timezone

        from coldfront_billing.models import BillingScheduleSettings

        settings = BillingScheduleSettings.objects.create(
            scheduling_enabled=False,
            start_date=timezone.localdate(),
            notification_email='billing@tufts.com',
        )
        mock_msg = MagicMock()
        mock_msg.send.side_effect = OSError('smtp error')
        mock_email_class.return_value = mock_msg
        result = send_billing_report_email(settings)
        assert result['success'] is False
        assert 'smtp error' in result['message']
