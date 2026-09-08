from django.core.mail import EmailMessage

from coldfront_billing.models import BillingScheduleHistory, BillingScheduleSettings
from coldfront_billing.reports.csv import create_csv_report
from coldfront_billing.settings import BILLING_EMAIL_FROM
from coldfront_billing.utils import NoStorageException, get_month_abbr, validate_emails

EMAIL_SUBJECT = 'Billing monthly report'
EMAIL_BODY = 'Attached is the latest CSV report.'


def create_failed_mail_response(message: str):
    return {
        'success': False,
        'message': message,
        'history_status': BillingScheduleHistory.Status.FAILED_MAIL,
    }


def send_billing_report_email(billing_settings: BillingScheduleSettings):
    if not billing_settings or not billing_settings.notification_email:
        return create_failed_mail_response('No email address configured')

    valid_recipients, invalid_recipients = validate_emails(billing_settings.notification_email)

    if invalid_recipients:
        return create_failed_mail_response(f'Invalid email addresses: {", ".join(invalid_recipients)}')

    if not valid_recipients:
        return create_failed_mail_response('No valid email addresses found')

    try:
        filename, csv_content = create_csv_report()
    except NoStorageException:
        return {
            'success': False,
            'message': 'No storage resource found',
            'history_status': BillingScheduleHistory.Status.FAILED_REPORT,
        }
    except Exception as exc:
        return {
            'success': False,
            'message': f'Report generation failed: {exc}',
            'history_status': BillingScheduleHistory.Status.FAILED_REPORT,
        }

    subject = (billing_settings.email_subject or '').strip() or EMAIL_SUBJECT
    body = (billing_settings.email_content or '').strip() or EMAIL_BODY

    email = EmailMessage(
        subject=f'{subject} [{get_month_abbr()}]',
        body=body,
        from_email=BILLING_EMAIL_FROM,
        to=valid_recipients,
    )
    email.attach(filename, csv_content, 'text/csv')
    try:
        email.send()
    except Exception as exc:
        return create_failed_mail_response(f'Email send failed: {exc}')

    return {
        'success': True,
        'message': 'Email with attachment sent!',
    }
