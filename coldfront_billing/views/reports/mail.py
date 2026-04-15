import re

from django.conf import settings
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.mail import EmailMessage
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.views import View
from email_validator import EmailNotValidError, validate_email

from coldfront_billing.utils import NoStorageException
from coldfront_billing.views.reports.create import CreateReportMixin

EMAIL_FROM = getattr(
    settings,
    'COLDFRONT_BILLING_EMAIL_FROM',
    'billing@tufts.com',
)

EMAIL_SUBJECT = 'Billing monthly report'
EMAIL_BODY = 'Attached is the latest CSV report.'
EMAIL_TO = 'mh@tufts.com;admin@tufts.com'


class SendReportView(UserPassesTestMixin, CreateReportMixin, View):
    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        return HttpResponseForbidden('You are not allowed to access this resource.')

    def get(self, request, *args, **kwargs):
        email_to = re.split(r'[;,]', EMAIL_TO)

        valid_recipients = []
        invalid_recipients = []

        for email in email_to:
            email = email.strip()
            if not email:
                continue
            try:
                valid = validate_email(email)
                valid_recipients.append(valid.normalized)
            except EmailNotValidError:
                invalid_recipients.append(email)

        if invalid_recipients:
            return HttpResponse(f'Invalid email addresses: {", ".join(invalid_recipients)}')
        if not valid_recipients:
            return HttpResponse('No valid email addresses found')

        try:
            filename, csv_content = self.create_report()
        except NoStorageException:
            return HttpResponseNotFound('No storage resource found')

        email = EmailMessage(
            subject=EMAIL_SUBJECT,
            body=EMAIL_BODY,
            from_email=EMAIL_FROM,
            to=valid_recipients,
        )

        email.attach(filename, csv_content, 'text/csv')
        email.send()

        return HttpResponse('Email with attachment sent!')
