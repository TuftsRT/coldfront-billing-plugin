from django.utils import timezone
from django_q.models import Schedule

from coldfront_billing.constants import BILLING_SCHEDULE_NAME


def run_scheduled_billing_report():
    from coldfront_billing.models import BillingScheduleSettings
    from coldfront_billing.reports.mail import send_billing_report_email

    billing_settings = BillingScheduleSettings.objects.first()
    if not billing_settings:
        return {'success': False, 'message': 'No billing settings found'}

    today = timezone.localdate()

    if billing_settings.end_date and today > billing_settings.end_date:
        Schedule.objects.filter(name=BILLING_SCHEDULE_NAME).delete()
        return {'success': False, 'message': 'Schedule expired'}

    return send_billing_report_email(billing_settings)
