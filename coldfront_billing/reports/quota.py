from coldfront.core.project.models import Project

from coldfront_billing.allotments import create_or_update_allotment
from coldfront_billing.data.quota import NoCostQuotaEngine
from coldfront_billing.enums import AllocationStatus
from coldfront_billing.prefetch import (
    get_filtered_allocations_prefetch,
    get_projects_prefetch,
)
from coldfront_billing.views.no_cost_quota.common import quota_with_remaining


def auto_assign_quota() -> tuple[str, str]:
    """
    For each PI that appears on a prefetched billing project, distribute their
    remaining no-cost quota across their PI projects using the same rules as
    AssignNoCostQuotasView (NoCostQuotaEngine) and persist via create_or_update_allotment
    (AutoAssignAllotmentsView).
    """
    projects = get_projects_prefetch(Project.objects.all())

    processed = 0
    assignments_applied = 0

    for user_id in {p.pi_id for p in projects if p.pi_id}:
        for quota in quota_with_remaining.filter(user_id=user_id):
            remaining = round(quota.remaining, 2)
            if remaining <= 0:
                continue

            base_allocations = get_filtered_allocations_prefetch(quota)

            auto_assign_allocations = base_allocations.filter(
                status__name=AllocationStatus.ACTIVE,
                project__in=Project.objects.filter(pi=quota.user),
            )

            if not auto_assign_allocations.exists():
                continue

            engine = NoCostQuotaEngine(quota.user_id, auto_assign_allocations)
            assignements = engine.auto_assign(
                remaining,
                quota.units,
                quota.minimum_increment,
            )

            if not assignements:
                continue

            processed += 1
            for assignment in assignements:
                create_or_update_allotment(assignment.allocation_id, assignment.amount, quota)
                assignments_applied += 1

    if not processed:
        return 'skipped', 'No no-cost quotas auto-assigned (nothing to do or no eligible allocations).'

    return (
        'ok',
        f'Auto-assigned no-cost quota for {processed} quota(s); {assignments_applied} allotment(s) created or updated.',
    )
