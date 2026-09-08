import logging
from decimal import ROUND_CEILING, Decimal

from coldfront.core.allocation.models import Allocation
from coldfront.core.resource.models import Resource

from ..models import NoCostQuotaAllotment

logger = logging.getLogger(__name__)


def no_cost_quotas_report(username: str = None, username_exact: bool = False):
    """
    get info about no cost quotas for a given allocation.
    """
    data = []
    errors = []
    requires_payment = Resource.objects.filter(requires_payment=True, resource_type__name='Storage')
    shared_allotments = []
    if username:
        # only show allocations owned by the user (user is the PI of the project)
        if username_exact:
            allocations = (
                Allocation.objects.filter(
                    resources__in=requires_payment, status__name='Active', project__pi__username=username
                )
                .order_by('project__pi__username', 'project__title')
                .prefetch_related('allocationattribute_set', 'no_cost_quota_allotments')
            )
        else:
            allocations = (
                Allocation.objects.filter(
                    resources__in=requires_payment, status__name='Active', project__pi__username__istartswith=username
                )
                .order_by('project__pi__username', 'project__title')
                .prefetch_related('allocationattribute_set', 'no_cost_quota_allotments')
            )
    else:
        allocations = (
            Allocation.objects.filter(resources__in=requires_payment, status__name='Active')
            .order_by('project__pi__username', 'project__title')
            .prefetch_related('allocationattribute_set', 'no_cost_quota_allotments')
        )

    for allocation in allocations:
        try:
            vol_path = (
                allocation.allocationattribute_set.filter(allocation_attribute_type__name='sf_vol_path').first().value
            )
            quota = (
                allocation.allocationattribute_set.filter(allocation_attribute_type__name='reported_usage_bytes')
                .first()
                .value
            )
        except AttributeError:
            errors.append(f'Allocation {allocation.id} does not have required attributes.')
            continue
        storage_owner = allocation.project.pi.username
        info = {
            'allocation': allocation,
            'vol_path': vol_path,
            'storage_owner': storage_owner,
            'quota': f'{int(quota) / 10**12:.5f}',
            'allotments': [],
        }
        ncq_allotment = allocation.no_cost_quota_allotments.all()
        ncq_allot_total = Decimal(0)
        for allot in ncq_allotment:
            amount = allot.amount_tb
            ncq_allot_total += amount
            ncq = allot.no_cost_quota
            quota_type = ncq.quota_type
            ncq_owner = ncq.user.username
            info['allotments'].append({'amount': str(amount), 'quota_type': quota_type, 'ncq_owner': ncq_owner})
        info['ncq_allot_total'] = str(ncq_allot_total)
        info['billable_quota'] = f'{max(0, Decimal(int(quota) / 10**12) - ncq_allot_total):.5f}'
        data.append(info)
    if username and username_exact:
        # also look for any NoCostQuotaAllotments that the user owns, but are not associated with an allocation that they own
        ncq_allotments = NoCostQuotaAllotment.objects.filter(no_cost_quota__user__username=username).exclude(
            allocation__project__pi__username=username
        )
        if ncq_allotments.exists():
            for allot in ncq_allotments:
                allocation = allot.allocation
                vol_path = (
                    allocation.allocationattribute_set.filter(allocation_attribute_type__name='sf_vol_path')
                    .first()
                    .value
                )
                quota = (
                    allocation.allocationattribute_set.filter(allocation_attribute_type__name='reported_usage_bytes')
                    .first()
                    .value
                )
                storage_owner = allocation.project.pi.username
                amount = str(allot.amount_tb)
                ncq_owner = allot.no_cost_quota.user.username
                quota_type = allot.no_cost_quota.quota_type
                shared_allotments.append(
                    {
                        'allocation': allocation,
                        'vol_path': vol_path,
                        'storage_owner': storage_owner,
                        'quota': f'{int(quota) / 10**12:.5f}',
                        'amount': amount,
                        'ncq_owner': ncq_owner,
                        'quota_type': quota_type,
                    }
                )
    return {'allocations': data, 'shared_allotments': shared_allotments, 'errors': errors}


def get_oversubscribed_no_cost_quotas():
    """
    return any NoCostQuotaAllotments that are associated with an allocation where allotment total exceeds allocation quota.
    """
    requires_payment = Resource.objects.filter(requires_payment=True, resource_type__name='Storage')
    allocations = Allocation.objects.filter(resources__in=requires_payment, status__name='Active').prefetch_related(
        'allocationattribute_set'
    )
    exceeded_allotments = []
    for allocation in allocations:
        try:
            quota = (
                allocation.allocationattribute_set.filter(allocation_attribute_type__name='reported_quota_bytes')
                .first()
                .value
            )
        except AttributeError:
            print(f'Allocation {allocation.id} does not have required attributes.')
            continue
        ncq_allotment = NoCostQuotaAllotment.objects.filter(allocation=allocation)
        if not ncq_allotment.exists():
            continue
        increment = Decimal(ncq_allotment.first().no_cost_quota.increment_gb) / Decimal(1000)
        ncq_allot_total = sum(allot.amount_tb for allot in ncq_allotment)
        total = Decimal(ncq_allot_total).quantize(increment, rounding=ROUND_CEILING)
        quota_tb = Decimal(int(quota) / 10**12)
        if quota_tb < total:
            exceeded_allotments.append(
                {
                    'allocation': allocation,
                    'quota': quota_tb,
                    'total_allotments': total,
                    'ncq_allotments': ncq_allotment,
                }
            )
    return exceeded_allotments


def expired_storage_allocations_with_ncq_allotments():
    """
    get info about storage allocations that have expired and require payment, including the vol_path and the storage owner.
    """
    storage = Resource.objects.filter(resource_type__name='Storage')
    expired_allocations = (
        Allocation.objects.filter(resources__in=storage)
        .exclude(status__name='Active')
        .prefetch_related('allocationattribute_set', 'project__pi')
    )
    data = []
    for allocation in expired_allocations:
        ncq_allotment = NoCostQuotaAllotment.objects.filter(allocation=allocation)
        if ncq_allotment.exists():
            vol_path = (
                allocation.allocationattribute_set.filter(allocation_attribute_type__name='sf_vol_path').first().value
            )
            storage_owner = allocation.project.pi.username
            resource = allocation.resources
            resource_name = resource.first().name if resource.exists() else ''
            requires_payment = resource.first().requires_payment if resource.exists() else False
            status = allocation.status.name

            data.append(
                {
                    'owner': storage_owner,
                    'resource': resource_name,
                    'vol_path': vol_path,
                    'requires_payment': requires_payment,
                    'status': status,
                    'allocation': allocation,
                    'ncq_allotments': ncq_allotment,
                }
            )
    return data
