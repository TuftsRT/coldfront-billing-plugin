import logging

from django.utils import timezone
from django_q.models import Schedule

from coldfront_billing.allotments import reduce_allotments_evenly
from coldfront_billing.constants import BILLING_SCHEDULE_NAME
from coldfront_billing.models import BillingScheduleHistory, BillingScheduleSettings
from coldfront_billing.models.no_cost_quota import NoCostQuotaAllotment, quota_with_remaining
from coldfront_billing.reports import auto_assign_quota, get_oversubscribed_no_cost_quotas, send_billing_report_email
from coldfront_billing.reports.nocostquota import no_cost_quotas_report

logger = logging.getLogger(__name__)


def run_scheduled_billing_report():
    billing_settings = BillingScheduleSettings.objects.first()
    if not billing_settings:
        return {'success': False, 'message': 'No billing settings found'}

    today = timezone.localdate()

    if billing_settings.end_date and today > billing_settings.end_date:
        Schedule.objects.filter(name=BILLING_SCHEDULE_NAME).delete()
        return {'success': False, 'message': 'Schedule expired'}

    started = timezone.now()

    if billing_settings.autoassign_no_cost_quota:
        try:
            auto_assign_quota()
        except Exception as exc:
            BillingScheduleHistory.objects.create(
                started=started,
                stopped=timezone.now(),
                status=BillingScheduleHistory.Status.FAILED_AUTOASSIGN,
                details=str(exc),
            )
            return {'success': False, 'message': f'Auto-assign failed: {exc}'}

    result = send_billing_report_email(billing_settings)
    stopped = timezone.now()
    if success := result.get('success'):
        history_status = BillingScheduleHistory.Status.SUCCESS
    else:
        history_status = result.get(
            'history_status',
            BillingScheduleHistory.Status.FAILED_MAIL,
        )
    details = '' if success else result.get('message', '')

    BillingScheduleHistory.objects.create(
        started=started,
        stopped=stopped,
        status=history_status,
        details=details,
    )
    return result


def send_ncq_report():
    report = no_cost_quotas_report()
    for i in report['allocations']:
        del i['allocation']  # remove allocation object from report to avoid serialization issues

    ncq_remaining_report = []
    for i in quota_with_remaining:
        ncq_remaining_report.append(
            {
                'user': i.user.username,
                'quota_type': i.quota_type,
                'amount': i.amount_tb,
                'remaining': round(i.remaining, 2),
            }
        )
    return ncq_remaining_report


def fix_oversubscribed_no_cost_quotas():
    """
    Fix any NoCostQuotaAllotments that are associated with an allocation where allotment total exceeds allocation quota.
    """
    exceeded_allotments = get_oversubscribed_no_cost_quotas()
    for item in exceeded_allotments:
        reduce_allotments_evenly(list(item['ncq_allotments']))
    return [item['ncq_allotments'] for item in exceeded_allotments]


def remove_empty_ncq_allotments():
    empty_allotments = NoCostQuotaAllotment.objects.filter(amount_tb__lte=0)
    count = empty_allotments.count()
    if count > 0:
        logger.info(f'Removing {count} NoCostQuotaAllotment(s) with amount 0.')
        empty_allotments.delete()
    return f'Removed {count} NoCostQuotaAllotment(s) with amount 0.'


def autoallocate_ncq_allotments():
    """
    Automatically allocate NoCostQuotaAllotments to eligible users based on their remaining quota.
    """
    logger.info('Starting automatic allocation of NoCostQuotaAllotments.')
    response = auto_assign_quota()
    logger.info(f'Automatic allocation response: {response}')
    return response
