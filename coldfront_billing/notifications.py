import logging

from coldfront.core.allocation.models import (
    Allocation,
    AllocationAttributeChangeRequest,
    AllocationChangeRequest,
)
from coldfront.core.resource.models import ResourceType
from django.core.mail import EmailMessage

from coldfront_billing.constants import DEFAULT_BILLING_COST, DEFAULT_BILLING_QUOTA, QUOTA_ATTR_NAME
from coldfront_billing.data import BillingAllocation
from coldfront_billing.prefetch import (
    get_no_cost_quota_allotments_prefetch,
    get_paid_storage_resources_prefetch,
    get_quota_attr_prefetch,
    is_paid_storage_allocation,
)
from coldfront_billing.settings import (
    BILLING_ALLOCATION_EMAIL_BODY,
    BILLING_ALLOCATION_EMAIL_SUBJECT,
    BILLING_EMAIL_FROM,
)

logger = logging.getLogger(__name__)


def create_recipient_list(
    allocation: Allocation,
    allocation_change_pk: int | None = None,
) -> list[str]:
    project_owner = allocation.project.pi

    if allocation_change_pk is not None:
        record = AllocationChangeRequest.history.filter(id=allocation_change_pk).order_by('history_date').first()
    else:
        record = allocation.history.order_by('history_date').first()

    requester = record.history_user if record else None

    return [
        email
        for email in {
            project_owner.email,
            requester.email if requester and requester.pk != project_owner.pk else None,
        }
        if email
    ]


def calculate_cost(allocation_pk) -> float:
    storage_type = ResourceType.objects.only('id').filter(name='Storage').first()
    if not storage_type:
        return 0.0
    prefetched = (
        Allocation.objects.filter(pk=allocation_pk)
        .prefetch_related(
            get_quota_attr_prefetch(),
            get_paid_storage_resources_prefetch(storage_type.id),
            get_no_cost_quota_allotments_prefetch(),
        )
        .first()
    )
    return (
        BillingAllocation.parse(prefetched, DEFAULT_BILLING_QUOTA, DEFAULT_BILLING_COST).total_cost
        if prefetched is not None
        else 0.0
    )


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

    if (cost := calculate_cost(allocation.pk)) <= 0:
        return

    recipient_list = create_recipient_list(allocation, allocation_change_pk)
    if not recipient_list:
        logger.warning(
            f'Skipping allocation quota approval email for allocation {allocation.pk}: no recipient addresses',
        )
        return

    project_name = allocation.project.title
    subject = BILLING_ALLOCATION_EMAIL_SUBJECT.format(
        project_name=project_name,
    )
    body = BILLING_ALLOCATION_EMAIL_BODY.format(
        project_name=project_name,
        quota_amount=quota_amount,
        cost=f'{cost:.2f}',
    )

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
