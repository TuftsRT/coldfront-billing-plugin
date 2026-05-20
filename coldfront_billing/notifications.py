import logging

from coldfront.core.allocation.models import (
    Allocation,
    AllocationAttributeChangeRequest,
    AllocationChangeRequest,
)
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage

from coldfront_billing.constants import (
    QUOTA_ATTR_NAME,
)
from coldfront_billing.prefetch import is_paid_storage_allocation
from coldfront_billing.settings import (
    BILLING_ALLOCATION_EMAIL_BODY,
    BILLING_ALLOCATION_EMAIL_SUBJECT,
    BILLING_EMAIL_FROM,
)

User = get_user_model()
logger = logging.getLogger(__name__)


def _get_allocation_requester(allocation: Allocation) -> User | None:
    record = allocation.history.order_by('history_date').first()
    if record is None:
        return None
    return record.history_user


def _get_change_request_requester(allocation_change_pk: int) -> User | None:
    record = AllocationChangeRequest.history.filter(id=allocation_change_pk).order_by('history_date').first()
    if record is None:
        return None
    return record.history_user


def _recipient_emails(project_owner: User, requester: User | None) -> list[str]:
    emails: list[str] = []
    if project_owner.email:
        emails.append(project_owner.email)
    if requester and requester.pk != project_owner.pk and requester.email:
        emails.append(requester.email)
    return emails


def send_allocation_notification(
    allocation: Allocation,
    *,
    allocation_change_pk: int | None = None,
) -> None:
    """Notify project owner and requester when a paid storage allocation quota is approved."""

    if not is_paid_storage_allocation(allocation):
        return

    if (
        allocation_change_pk is not None
        and not AllocationAttributeChangeRequest.objects.filter(
            allocation_change_request_id=allocation_change_pk,
            allocation_attribute__allocation_attribute_type__name=QUOTA_ATTR_NAME,
        ).exists()
    ):
        # change request is not for quota attribute
        return

    quota_amount = allocation.get_attribute(QUOTA_ATTR_NAME, typed=False)
    if quota_amount is None:
        return

    project = allocation.project
    project_owner = project.pi
    requester = (
        _get_change_request_requester(allocation_change_pk)
        if allocation_change_pk is not None
        else _get_allocation_requester(allocation)
    )
    recipient_list = _recipient_emails(project_owner, requester)
    if not recipient_list:
        logger.warning(
            'Skipping allocation quota approval email for allocation %s: no recipient addresses',
            allocation.pk,
        )
        return

    project_name = project.title
    subject = BILLING_ALLOCATION_EMAIL_SUBJECT.format(project_name=project_name)
    body = BILLING_ALLOCATION_EMAIL_BODY.format(project_name=project_name, quota_amount=quota_amount)

    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=BILLING_EMAIL_FROM,
        to=recipient_list,
    )
    try:
        email.send()
    except Exception:
        logger.exception(
            'Failed to send allocation quota approval email for allocation %s to %s',
            allocation.pk,
            recipient_list,
        )
