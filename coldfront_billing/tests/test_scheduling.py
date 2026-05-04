from unittest.mock import patch

import pytest
from django.utils import timezone
from django_q.models import Schedule

from coldfront_billing.models import BillingScheduleSettings
from coldfront_billing.scheduling import BILLING_SCHEDULE_NAME, sync_billing_schedule


@pytest.mark.django_db
class TestSyncBillingSchedule:
    def _settings(self, **overrides):
        BillingScheduleSettings.objects.all().delete()
        Schedule.objects.filter(name=BILLING_SCHEDULE_NAME).delete()
        defaults = {
            'scheduling_enabled': True,
            'start_date': timezone.localdate(),
            'notification_email': 'a@test.local',
        }
        defaults.update(overrides)
        return BillingScheduleSettings.objects.create(**defaults)

    def test_every_5_minutes_uses_django_q_minutes_type(self):
        with (
            patch('coldfront_billing.scheduling.BILLING_USE_TEST_SCHEDULING', True),
            patch('coldfront_billing.forms.schedule.BILLING_USE_TEST_SCHEDULING', True),
            patch('coldfront_billing.models.schedule.BILLING_USE_TEST_SCHEDULING', True),
        ):
            s = self._settings()
            assert s.get_schedule() == BillingScheduleSettings.SCHEDULE_EVERY_5_MINUTES
            sync_billing_schedule(s)
            q = Schedule.objects.get(name=BILLING_SCHEDULE_NAME)
            assert q.schedule_type == Schedule.MINUTES
            assert q.minutes == 5

    def test_monthly_clears_minutes_field(self):
        s = self._settings()
        assert s.get_schedule() == BillingScheduleSettings.SCHEDULE_MONTHLY
        sync_billing_schedule(s)
        q = Schedule.objects.get(name=BILLING_SCHEDULE_NAME)
        assert q.schedule_type == Schedule.MONTHLY
        assert q.minutes is None
