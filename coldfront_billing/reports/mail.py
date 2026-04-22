from django.conf import settings
from django.core.mail import EmailMessage

from coldfront_billing.models import BillingScheduleSettings
from coldfront_billing.reports import create_csv_report
from coldfront_billing.utils import NoStorageException, get_month_abbr, validate_emails

EMAIL_FROM = getattr(
    settings,
    'COLDFRONT_BILLING_EMAIL_FROM',
    'billing@tufts.com',
)

EMAIL_SUBJECT = 'Billing monthly report'
EMAIL_BODY = 'Attached is the latest CSV report.'


def send_billing_report_email(billing_settings: BillingScheduleSettings):
    if not billing_settings or not billing_settings.notification_email:
        return {
            'success': False,
            'message': 'No email address configured',
        }

    valid_recipients, invalid_recipients = validate_emails(billing_settings.notification_email)

    if invalid_recipients:
        return {
            'success': False,
            'message': f'Invalid email addresses: {", ".join(invalid_recipients)}',
        }

    if not valid_recipients:
        return {
            'success': False,
            'message': 'No valid email addresses found',
        }

    try:
        filename, csv_content = create_csv_report()
    except NoStorageException:
        return {
            'success': False,
            'message': 'No storage resource found',
        }

    subject = (billing_settings.email_subject or '').strip() or EMAIL_SUBJECT
    body = (billing_settings.email_content or '').strip() or EMAIL_BODY

    email = EmailMessage(
        subject=f'{subject} [{get_month_abbr()}]',
        body=body,
        from_email=EMAIL_FROM,
        to=valid_recipients,
    )
    email.attach(filename, csv_content, 'text/csv')
    email.send()

    return {
        'success': True,
        'message': 'Email with attachment sent!',
    }
