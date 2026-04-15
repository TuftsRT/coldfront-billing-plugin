"""Tests for SendReportView (email billing report)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse

from coldfront_billing.utils import NoStorageException
from coldfront_billing.views.reports.mail import SendReportView

REVERSE = 'reports_send'


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

    @patch('coldfront_billing.views.reports.mail.EMAIL_TO', 'bad@@example.com')
    def test_invalid_recipients_message(self, client, superuser):
        client.force_login(superuser)
        response = client.get(reverse(REVERSE))
        assert response.status_code == 200
        assert b'Invalid email addresses' in response.content
        assert b'bad@@example.com' in response.content

    @patch('coldfront_billing.views.reports.mail.EMAIL_TO', '  ;  ,  ')
    def test_no_valid_recipients_message(self, client, superuser):
        client.force_login(superuser)
        response = client.get(reverse(REVERSE))
        assert response.status_code == 200
        assert response.content == b'No valid email addresses found'

    def test_superuser_no_storage_returns_404(self, client, superuser):
        client.force_login(superuser)
        with (
            patch('coldfront_billing.views.reports.mail.EMAIL_TO', 'noreply@test.local'),
            patch(
                'coldfront_billing.views.reports.mail.validate_email',
                return_value=SimpleNamespace(normalized='noreply@test.local'),
            ),
            patch.object(
                SendReportView,
                'get_projects_prefetch',
                side_effect=NoStorageException(),
            ),
        ):
            response = client.get(reverse(REVERSE))
        assert response.status_code == 404
        assert response.content == b'No storage resource found'

    def test_superuser_sends_email_with_attachment(self, client, superuser):
        client.force_login(superuser)
        mock_msg = MagicMock()
        with (
            patch('coldfront_billing.views.reports.mail.EMAIL_TO', 'noreply@test.local'),
            patch(
                'coldfront_billing.views.reports.mail.validate_email',
                return_value=SimpleNamespace(normalized='noreply@test.local'),
            ),
            patch.object(
                SendReportView,
                'create_report',
                return_value=('billing.csv', 'h1,h2\n1,2\n'),
            ),
            patch('coldfront_billing.views.reports.mail.EmailMessage') as mock_email_class,
        ):
            mock_email_class.return_value = mock_msg
            response = client.get(reverse(REVERSE))

        assert response.status_code == 200
        assert response.content == b'Email with attachment sent!'
        mock_email_class.assert_called_once()
        kwargs = mock_email_class.call_args.kwargs
        assert kwargs['subject'] == 'Billing monthly report'
        assert kwargs['body'] == 'Attached is the latest CSV report.'
        assert kwargs['to'] == ['noreply@test.local']
        mock_msg.attach.assert_called_once_with('billing.csv', 'h1,h2\n1,2\n', 'text/csv')
        mock_msg.send.assert_called_once()
