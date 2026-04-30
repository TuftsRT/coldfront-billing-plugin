from django.utils import timezone
from django_q.models import Schedule


def run_scheduled_billing_report():
    from coldfront_billing.constants import BILLING_SCHEDULE_NAME
    from coldfront_billing.models import BillingScheduleHistory, BillingScheduleSettings
    from coldfront_billing.reports import auto_assign_quota, send_billing_report_email

    billing_settings = BillingScheduleSettings.objects.first()
    if not billing_settings:
        return {'success': False, 'message': 'No billing settings found'}

    today = timezone.localdate()

    if billing_settings.end_date and today > billing_settings.end_date:
        Schedule.objects.filter(name=BILLING_SCHEDULE_NAME).delete()
        return {'success': False, 'message': 'Schedule expired'}

    started = timezone.now()

    if billing_settings.autoassign_no_cost_quota:
        try:
            auto_assign_quota()
        except Exception as exc:
            BillingScheduleHistory.objects.create(
                started=started,
                stopped=timezone.now(),
                status=BillingScheduleHistory.Status.FAILED_AUTOASSIGN,
                details=str(exc),
            )
            return {'success': False, 'message': f'Auto-assign failed: {exc}'}

    result = send_billing_report_email(billing_settings)
    stopped = timezone.now()
    if success := result.get('success'):
        history_status = BillingScheduleHistory.Status.SUCCESS
    else:
        history_status = result.get(
            'history_status',
            BillingScheduleHistory.Status.FAILED_MAIL,
        )
    details = '' if success else result.get('message', '')

    BillingScheduleHistory.objects.create(
        started=started,
        stopped=stopped,
        status=history_status,
        details=details,
    )
    return result
