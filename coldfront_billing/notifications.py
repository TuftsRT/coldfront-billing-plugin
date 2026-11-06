import logging
from decimal import Decimal

from django.core.mail import EmailMessage

from coldfront.core.allocation.models import (
    Allocation,
    AllocationAttributeChangeRequest,
    AllocationChangeRequest,
)
from coldfront.core.resource.models import ResourceType

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
    BILLING_ALLOCATION_EMAIL_NO_COST_PENDING,
    BILLING_ALLOCATION_EMAIL_SUBJECT,
    BILLING_EMAIL_FROM,
    allocation_email_enabled,
)

logger = logging.getLogger(__name__)


def create_recipient_list(
    allocation: Allocation,
    allocation_change_pk: int | None = None,
) -> list[str]:
    project_owner = allocation.project.pi

    if allocation_change_pk is not None:
        record = AllocationChangeRequest.history.filter(id=allocation_change_pk).order_by("history_date").first()
    else:
        record = allocation.history.order_by("history_date").first()

    requester = record.history_user if record else None

    return [
        email
        for email in {
            project_owner.email,
            requester.email if requester and requester.pk != project_owner.pk else None,
        }
        if email
    ]


def calculate_cost(allocation_pk) -> Decimal:
    storage_type = ResourceType.objects.only("id").filter(name="Storage").first()
    if not storage_type:
        return Decimal("0.00")
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
        else Decimal("0.00")
    )


def send_allocation_notification(
    allocation: Allocation,
    *,
    allocation_change_pk: int | None = None,
    no_cost_quota_pending: bool = False,
) -> None:
    """
    Notify project owner and requester when a paid storage allocation quota is approved.

    `no_cost_quota_pending` says a no-cost quota they asked to apply couldn't be applied
    automatically, so the cost quoted leaves it out; the email then says it's still to come.

    Does nothing unless allocation_email_enabled(): by default that follows ColdFront's
    EMAIL_ENABLED.
    """

    if not allocation_email_enabled():
        logger.info(f"Allocation quota approval emails are disabled; not emailing about allocation {allocation.pk}")
        return

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
            f"Skipping allocation quota approval email for allocation {allocation.pk}: no recipient addresses",
        )
        return

    project_name = allocation.project.title
    subject = BILLING_ALLOCATION_EMAIL_SUBJECT.format(
        project_name=project_name,
    )
    placeholders = {"project_name": project_name, "quota_amount": quota_amount, "cost": f"{cost:.2f}"}
    body = BILLING_ALLOCATION_EMAIL_BODY.format(**placeholders)
    if no_cost_quota_pending:
        body = f"{body}\n\n{BILLING_ALLOCATION_EMAIL_NO_COST_PENDING.format(**placeholders)}"

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
            "Failed to send allocation quota approval email for allocation %s to %s",
            allocation.pk,
            recipient_list,
        )
