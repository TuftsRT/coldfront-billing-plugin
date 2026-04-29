from django.utils import timezone
from django_q.models import Schedule


def run_scheduled_billing_report():
    from coldfront_billing.constants import BILLING_SCHEDULE_NAME
    from coldfront_billing.models import BillingScheduleSettings
    from coldfront_billing.reports import auto_assign_quota, send_billing_report_email

    billing_settings = BillingScheduleSettings.objects.first()
    if not billing_settings:
        return {'success': False, 'message': 'No billing settings found'}

    today = timezone.localdate()

    if billing_settings.end_date and today > billing_settings.end_date:
        Schedule.objects.filter(name=BILLING_SCHEDULE_NAME).delete()
        return {'success': False, 'message': 'Schedule expired'}

    if billing_settings.autoassign_no_cost_quota:
        auto_assign_quota()

    return send_billing_report_email(billing_settings)
