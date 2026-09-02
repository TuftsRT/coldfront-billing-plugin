from decimal import ROUND_CEILING, Decimal
import logging

from django.db.models import TextField
from django.db.models.functions import Cast
from django.core.exceptions import ObjectDoesNotExist
from django.utils.timezone import localdate

from coldfront.core.allocation.models import Allocation, AllocationAttribute
from coldfront.core.resource.models import Resource
from coldfront.core.project.models import Project

from ..models import CostCenterAssignment
from ..constants import BILLING_ATTRIBUTE_NAME
from ..data.billing import create_billing_allocations
from ..prefetch import get_billing_visible_projects_query, get_projects_prefetch

logger = logging.getLogger(__name__)


def missing_billing_code_report(username: str = None, username_exact: bool = False):
    """
    get info about missing billing codes for all allocations requiring payment.
    """

    month = localdate().strftime("%Y-%m")
    if username:
        if username_exact:
            projects = get_projects_prefetch(Project.objects.filter(get_billing_visible_projects_query(username)))
        else:
            projects = get_projects_prefetch(Project.objects.filter(pi__username__istartswith=username))
    else:
        projects = get_projects_prefetch(Project.objects.all().order_by('pi__username', 'title'))
    total_cost = 0
    missing_billing_code = []
    for project in projects:
        billing_allocations = create_billing_allocations(getattr(project, BILLING_ATTRIBUTE_NAME, []))
        project_cost = sum(b.total_cost for b in billing_allocations)

        # only report projects with a cost
        if project_cost:
            try:
                assignments = project.cost_center_assignment.assignments or []
                if len(assignments) == 0:
                    total_cost += project_cost
                    # if the project does not have a CostCenterAssignment, we need to report these projects as missing billing codes
                    missing_billing_code.append({'project': project, 'project_cost': project_cost})
            except ObjectDoesNotExist:
                total_cost += project_cost
                # if the project does not have a CostCenterAssignment, we need to report these projects as missing billing codes
                missing_billing_code.append({'project': project, 'project_cost': project_cost})

    return {"missing_billing_code": missing_billing_code, "total_cost": round(total_cost, 2), "month": month }


def get_cost_previews(username=None, billing_code=None, username_exact: bool = False):
    """
    get info about costs based on current billing allocations for all projects with a given billing code and/or owned by a given user.
    """
    month = localdate().strftime("%Y-%m")
    missing_billing_code = []
    if billing_code and username:
        if username_exact:
            projects = get_projects_prefetch(
                Project.objects.filter(
                    get_billing_visible_projects_query(username)).annotate(
                        json_as_text=Cast('cost_center_assignment__assignments', TextField())).filter(
                            json_as_text__icontains=f"\"{billing_code}")).order_by('pi__username', 'title')
        else:
            projects = get_projects_prefetch(
                Project.objects.filter(pi__username__istartswith=username).annotate(
                    json_as_text=Cast('cost_center_assignment__assignments', TextField())).filter(
                        json_as_text__icontains=f"\"{billing_code}")).order_by('pi__username', 'title')

    elif billing_code:
        projects = get_projects_prefetch(
            Project.objects.all().annotate(
                json_as_text=Cast('cost_center_assignment__assignments', TextField())).filter(
                    json_as_text__icontains=f"\"{billing_code}")).order_by('pi__username', 'title')
    elif username:
        if username_exact:
            projects = get_projects_prefetch(Project.objects.filter(get_billing_visible_projects_query(username))).order_by('pi__username', 'title')
        else:
            projects = get_projects_prefetch(Project.objects.filter(pi__username__istartswith=username).order_by('pi__username', 'title'))
    else:   
        projects = get_projects_prefetch(Project.objects.all().order_by('pi__username', 'title'))
    total_cost = Decimal('0')
    charge_report = []
    for project in projects:
        billing_allocations = create_billing_allocations(getattr(project, BILLING_ATTRIBUTE_NAME, []))
        project_cost = sum(b.total_cost for b in billing_allocations)
        for b in billing_allocations:
            b.ncq_applied = sum([i.amount_tb for i in b.no_cost_quotas])
                
        if not project_cost:
            continue
        total_cost += project_cost
        try:
            assignments = project.cost_center_assignment.assignments or []
        except ObjectDoesNotExist:
            # if the project does not have a CostCenterAssignment, we need to report these projects as missing billing codes
            missing_billing_code.append({'project': project, 'project_cost': project_cost})
            continue

        for assignment in sorted(assignments, key=lambda x: x.get('department')):
            dept_id = assignment.get('department')
            pct = assignment.get('percentage')
            grant = assignment.get('grant', '')
            cost = (project_cost * Decimal(int(pct) / 100)).quantize(Decimal('0.01'), rounding=ROUND_CEILING)
            charges = {
                'project': project,
                'allocations': billing_allocations,
                'department': dept_id,
                'grant': grant,
                'percentage': pct,
                'charged_to_id': cost,
                'project_cost': project_cost,
            }
            charge_report.append(charges)

    return {"missing_billing_code": missing_billing_code, "charge_report": charge_report, "total_cost": total_cost.quantize(Decimal('0.01'), rounding=ROUND_CEILING), "month": month }


def get_cost_per_allocation():
    rows = []
    projects = get_projects_prefetch(Project.objects.all().order_by('pi__username', 'title'))
    for project in projects:
        billing_allocations = create_billing_allocations(getattr(project, BILLING_ATTRIBUTE_NAME, []))
        for ba in billing_allocations:
            vol_path = AllocationAttribute.objects.filter(allocation_id=ba.allocation_id, allocation_attribute_type__name="sf_vol_path").first().value
            rows.append({
                'owner': ba.extra.get('pi_name'),
                'resource': ba.extra.get('resource_name'),
                'vol_path': vol_path,
                'quota_tb': ba.quota_tb,
                'cost_per_tb': ba.cost_per_tb,
                'cost': (Decimal(ba.quota_tb).quantize(Decimal('0.1'), rounding=ROUND_CEILING) * Decimal(ba.cost_per_tb).quantize(Decimal('0.01'), rounding=ROUND_CEILING)).quantize(Decimal('0.01'), rounding=ROUND_CEILING),
                'ncq_applied': sum([i.amount_tb for i in ba.no_cost_quotas]),
                'cost_after_ncq': ba.total_cost
            })
    return rows


def get_all_storage_allocations():
    """
    get info about storage allocations that have expired and require payment, including the vol_path and the storage owner.
    """
    storage = Resource.objects.filter(resource_type__name='Storage')
    allocations = Allocation.objects.filter(resources__in=storage).prefetch_related('allocationattribute_set', 'project__pi', 'no_cost_quota_allotments')
    data = []
    for allocation in allocations:
        vol_path_attr = allocation.allocationattribute_set.filter(allocation_attribute_type__name='sf_vol_path')
        vol_path = vol_path_attr.first().value if vol_path_attr.exists() else 'NA'
        quota_attr = allocation.allocationattribute_set.filter(allocation_attribute_type__name='reported_quota_bytes')
        if quota_attr.exists():
            quota = quota_attr.first().value
            quota = (Decimal(quota)/10**12).quantize(Decimal('0.01'), rounding=ROUND_CEILING)
        else:
            quota = 'NA'
        usage = allocation.allocationattribute_set.filter(allocation_attribute_type__name='reported_usage_bytes')
        if usage.exists():
            usage = usage.first().value
            usage = (Decimal(usage)/10**12).quantize(Decimal('0.0001'), rounding=ROUND_CEILING)
        else:
            usage = 'NA'
        storage_owner = allocation.project.pi.username
        resource = allocation.resources
        resource_name = resource.first().name if resource.exists() else ''
        requires_payment = resource.first().requires_payment if resource.exists() else False
        status = allocation.status.name
        ncq_allotment = allocation.no_cost_quota_allotments.all()
        if ncq_allotment.exists():
            for allot in ncq_allotment:
                data.append({'owner': storage_owner, 'resource': resource_name, 
                             'vol_path': vol_path, 'requires_payment': requires_payment, 
                             'status': status,  'quota': quota, 'usage': usage,
                             'ncq_owner': allot.no_cost_quota.user, 'ncq_amount': str(allot.amount_tb), 'ncq_quota_type': allot.no_cost_quota.quota_type})
        else:
            data.append({'owner': storage_owner, 'resource': resource_name, 
                         'vol_path': vol_path, 'requires_payment': requires_payment, 
                         'status': status,  'quota': quota, 'usage': usage,
                         'ncq_owner': None, 'ncq_amount': None, 'ncq_quota_type': None})
    return data
