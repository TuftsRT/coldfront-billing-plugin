"""Tests for SendReportView (email billing report)."""

from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from django.utils import timezone

from coldfront_billing.models import BillingScheduleSettings
from coldfront_billing.reports.mail import EMAIL_SUBJECT
from coldfront_billing.utils import NoStorageException

REVERSE = 'reports_send'


def _schedule_settings(**overrides):
    defaults = {
        'scheduling_enabled': True,
        'start_date': timezone.localdate(),
        'notification_email': 'noreply@test.local',
        'email_subject': '',
        'email_content': '',
        'autoassign_no_cost_quota': False,
    }
    defaults.update(overrides)
    BillingScheduleSettings.objects.all().delete()
    return BillingScheduleSettings.objects.create(**defaults)


@pytest.mark.django_db
@pytest.mark.usefixtures('configure_urls')
class TestSendReportView:
    def test_anonymous_forbidden(self, client):
        response = client.get(reverse(REVERSE))
        assert response.status_code == 403

    def test_regular_user_forbidden(self, client, user):
        client.force_login(user)
        response = client.get(reverse(REVERSE))
        assert response.status_code == 403
        assert b'not allowed' in response.content.lower()

    def test_invalid_recipients_message(self, client, superuser):
        _schedule_settings(notification_email='bad@@example.com')
        client.force_login(superuser)
        response = client.get(reverse(REVERSE))
        assert response.status_code == 400
        data = response.json()
        assert data['success'] is False
        assert 'Invalid email addresses' in data['message']
        assert 'bad@@example.com' in data['message']

    def test_no_valid_recipients_message(self, client, superuser):
        _schedule_settings(notification_email='  ;  ,  ')
        client.force_login(superuser)
        response = client.get(reverse(REVERSE))
        assert response.status_code == 400
        assert response.json() == {
            'success': False,
            'message': 'No valid email addresses found',
        }

    def test_superuser_no_storage_returns_400(self, client, superuser):
        _schedule_settings()
        client.force_login(superuser)
        with (
            patch(
                'coldfront_billing.reports.mail.validate_emails',
                return_value=(['noreply@test.local'], []),
            ),
            patch(
                'coldfront_billing.reports.mail.create_csv_report',
                side_effect=NoStorageException(),
            ),
        ):
            response = client.get(reverse(REVERSE))
        assert response.status_code == 400
        assert response.json() == {
            'success': False,
            'message': 'No storage resource found',
        }

    def test_superuser_sends_email_with_attachment(self, client, superuser):
        _schedule_settings()
        client.force_login(superuser)
        mock_msg = MagicMock()
        with (
            patch(
                'coldfront_billing.reports.mail.validate_emails',
                return_value=(['noreply@test.local'], []),
            ),
            patch(
                'coldfront_billing.reports.mail.create_csv_report',
                return_value=('billing.csv', 'h1,h2\n1,2\n'),
            ),
            patch(
                'coldfront_billing.reports.mail.get_month_abbr',
                return_value='APR',
            ),
            patch('coldfront_billing.reports.mail.EmailMessage') as mock_email_class,
        ):
            mock_email_class.return_value = mock_msg
            response = client.get(reverse(REVERSE))

        assert response.status_code == 200
        assert response.json() == {
            'success': True,
            'message': 'Email with attachment sent!',
        }
        mock_email_class.assert_called_once()
        kwargs = mock_email_class.call_args.kwargs
        assert kwargs['subject'] == f'{EMAIL_SUBJECT} [APR]'
        assert kwargs['body'] == 'Attached is the latest CSV report.'
        assert kwargs['to'] == ['noreply@test.local']
        mock_msg.attach.assert_called_once_with('billing.csv', 'h1,h2\n1,2\n', 'text/csv')
        mock_msg.send.assert_called_once()

    def test_custom_subject_and_body_from_settings(self, client, superuser):
        _schedule_settings(
            email_subject='Custom subject',
            email_content='Custom body line 1\nline 2',
        )
        client.force_login(superuser)
        mock_msg = MagicMock()
        with (
            patch(
                'coldfront_billing.reports.mail.validate_emails',
                return_value=(['noreply@test.local'], []),
            ),
            patch(
                'coldfront_billing.reports.mail.create_csv_report',
                return_value=('billing.csv', 'x'),
            ),
            patch(
                'coldfront_billing.reports.mail.get_month_abbr',
                return_value='APR',
            ),
            patch('coldfront_billing.reports.mail.EmailMessage') as mock_email_class,
        ):
            mock_email_class.return_value = mock_msg
            response = client.get(reverse(REVERSE))

        assert response.status_code == 200
        kwargs = mock_email_class.call_args.kwargs
        assert kwargs['subject'] == 'Custom subject [APR]'
        assert kwargs['body'] == 'Custom body line 1\nline 2'
