from datetime import date
from typing import Optional

from django.db import transaction
from django.utils import timezone
from django_q.models import Schedule

from coldfront_billing.constants import BILLING_REPORT_HOUR, BILLING_SCHEDULE_NAME, BILLING_USE_TEST_SCHEDULING
from coldfront_billing.models import BillingScheduleSettings
from coldfront_billing.tasks import run_scheduled_billing_report
from coldfront_billing.utils import calculate_next_run

BILLING_TASK_PATH = f'{run_scheduled_billing_report.__module__}.{run_scheduled_billing_report.__name__}'


def _calculate_repeats(
    minutes: Optional[int],
    next_run,
    end_date: Optional[date],
) -> int:
    """
    django-q decrements ``repeats`` after each run (when > 0). ``-1`` means forever.
    Count runs whose local calendar date is on or before ``end_date``, matching
    ``run_scheduled_billing_report``'s expiry check on ``timezone.localdate()``.
    """
    if end_date is None:
        return -1
    probe = Schedule(
        schedule_type=Schedule.MONTHLY,
        minutes=minutes,
        next_run=next_run,
    )
    count = 0
    current = next_run
    while timezone.localdate(current) <= end_date:
        count += 1
        nxt = probe.calculate_next_run(current)
        if nxt <= current:
            break
        current = nxt
    return count


@transaction.atomic
def sync_billing_schedule(billing_settings: Optional[BillingScheduleSettings]) -> None:
    # No settings row or disabled -> remove schedule if it exists
    if not billing_settings or not billing_settings.scheduling_enabled:
        Schedule.objects.filter(name=BILLING_SCHEDULE_NAME).delete()
        return

    # Build next_run from start_date
    kwargs = {'start_date': billing_settings.start_date}

    if BILLING_USE_TEST_SCHEDULING:
        kwargs.update(minutes=5)
    else:
        kwargs.update(hour=BILLING_REPORT_HOUR)
    next_run = calculate_next_run(**kwargs)

    if billing_settings.get_schedule() == BillingScheduleSettings.SCHEDULE_EVERY_5_MINUTES:
        schedule_type = Schedule.MINUTES
        minutes = 5
        repeats = -1
    else:
        schedule_type = Schedule.MONTHLY
        minutes = None
        repeats = _calculate_repeats(
            minutes,
            next_run,
            billing_settings.end_date,
        )

    Schedule.objects.update_or_create(
        name=BILLING_SCHEDULE_NAME,
        defaults={
            'func': BILLING_TASK_PATH,
            'schedule_type': schedule_type,
            'minutes': minutes,
            'next_run': next_run,
            'repeats': repeats,
        },
    )
