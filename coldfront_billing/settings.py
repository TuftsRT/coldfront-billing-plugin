from django.conf import settings

BILLING_EMAIL_FROM = getattr(
    settings,
    'COLDFRONT_BILLING_EMAIL_FROM',
    'billing@tufts.com',
)
BILLING_ALLOCATION_EMAIL_SUBJECT = getattr(
    settings,
    'COLDFRONT_BILLING_ALLOCATION_EMAIL_SUBJECT',
    'Storage quota updated for {project_name}',
)
BILLING_ALLOCATION_EMAIL_BODY = getattr(
    settings,
    'COLDFRONT_BILLING_ALLOCATION_EMAIL_BODY',
    'The storage quota amount for your project {project_name} has been changed to {quota_amount}. '
    'This new quota will incur a monthly cost of {cost}.',
)


def allocation_email_enabled() -> bool:
    """
    Whether to send the quota approval email: COLDFRONT_BILLING_ALLOCATION_EMAIL_ENABLED, or
    ColdFront's own EMAIL_ENABLED when that isn't set (or is None).

    Following EMAIL_ENABLED by default means the one switch that silences ColdFront's emails
    silences this one too; this email goes through Django's EmailMessage directly, so it would
    otherwise ignore that switch. Read on every call rather than at import, so a settings change
    or a test's override applies at once.
    """
    enabled = getattr(settings, 'COLDFRONT_BILLING_ALLOCATION_EMAIL_ENABLED', None)
    if enabled is None:
        enabled = getattr(settings, 'EMAIL_ENABLED', False)
    return bool(enabled)
