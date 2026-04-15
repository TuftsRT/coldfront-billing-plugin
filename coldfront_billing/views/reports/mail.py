from django.conf import settings
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.mail import EmailMessage
from django.http import JsonResponse
from django.views import View

from coldfront_billing.models import BillingScheduleSettings
from coldfront_billing.utils import NoStorageException, get_month_abbr, validate_emails
from coldfront_billing.views.reports.create import CreateReportMixin

EMAIL_FROM = getattr(
    settings,
    'COLDFRONT_BILLING_EMAIL_FROM',
    'billing@tufts.com',
)

EMAIL_SUBJECT = 'Billing monthly report'
EMAIL_BODY = 'Attached is the latest CSV report.'


class SendReportView(UserPassesTestMixin, CreateReportMixin, View):
    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        return JsonResponse(
            {
                'success': False,
                'message': 'You are not allowed to access this resource.',
            },
            status=403,
        )

    def get(self, *_, **__):
        billing_settings = BillingScheduleSettings.objects.first()

        if not billing_settings or not billing_settings.notification_email:
            return JsonResponse(
                {
                    'success': False,
                    'message': 'No email address configured',
                },
                status=400,
            )

        valid_recipients, invalid_recipients = validate_emails(billing_settings.notification_email)

        if invalid_recipients:
            return JsonResponse(
                {
                    'success': False,
                    'message': f'Invalid email addresses: {", ".join(invalid_recipients)}',
                },
                status=400,
            )
        if not valid_recipients:
            return JsonResponse(
                {
                    'success': False,
                    'message': 'No valid email addresses found',
                },
                status=400,
            )

        try:
            filename, csv_content = self.create_report()
        except NoStorageException:
            return JsonResponse(
                {
                    'success': False,
                    'message': 'No storage resource found',
                },
                status=404,
            )

        subject = (billing_settings.email_subject or '').strip() or EMAIL_SUBJECT
        body = (billing_settings.email_content or '').strip() or EMAIL_BODY

        email = EmailMessage(
            subject=subject + f' [{get_month_abbr()}]',
            body=body,
            from_email=EMAIL_FROM,
            to=valid_recipients,
        )

        email.attach(filename, csv_content, 'text/csv')
        email.send()

        return JsonResponse(
            {
                'success': True,
                'message': 'Email with attachment sent!',
            }
        )
