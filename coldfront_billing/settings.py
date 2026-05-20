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
