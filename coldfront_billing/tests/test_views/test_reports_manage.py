"""Tests for ManageReportsView."""

import pytest
from django.urls import reverse
from django.utils import timezone

from coldfront_billing.models import BillingScheduleSettings


def _manage_url():
    return reverse('reports_manage')


@pytest.mark.django_db
@pytest.mark.usefixtures('configure_urls')
class TestManageReportsView:
    def test_anonymous_redirected(self, client):
        response = client.get(_manage_url())
        assert response.status_code == 302
        assert '/login' in response.url

    def test_regular_user_forbidden(self, client, user):
        client.force_login(user)
        response = client.get(_manage_url())
        assert response.status_code == 403

    def test_superuser_creates_singleton_settings(self, client, superuser):
        BillingScheduleSettings.objects.all().delete()
        client.force_login(superuser)
        response = client.get(_manage_url())
        assert response.status_code == 200
        assert BillingScheduleSettings.objects.filter(pk=1).exists()
        assert 'schedule_settings' in response.context

    def test_superuser_can_update_settings(self, client, superuser):
        BillingScheduleSettings.objects.all().delete()
        client.force_login(superuser)
        response = client.post(
            _manage_url(),
            data={
                'scheduling_enabled': '',
                'start_date': timezone.localdate().isoformat(),
                'end_date': '',
                'notification_email': 'billing@tufts.com',
                'email_subject': 'Subject',
                'email_content': 'Body',
                'autoassign_no_cost_quota': '',
            },
        )
        assert response.status_code == 302
        settings = BillingScheduleSettings.objects.get(pk=1)
        assert settings.notification_email == 'billing@tufts.com'
