import math
from dataclasses import dataclass, field
from typing import Any, Dict, List

from coldfront_billing.constants import (
    NO_COST_QUOTA_DATA_ATTRIBUTE_NAME,
    QUOTA_ATTRIBUTE_NAME,
    STORAGE_RESOURCE_ATTRIBUTE_NAME,
)
from coldfront_billing.utils import parse_float

from .common import get_cost_per_tb
from .quota import BillingQuota


@dataclass
class BillingAllocation:
    allocation_id: int
    project_id: int
    quota_tb: int | float
    cost_per_tb: int | float
    extra: Dict[str, Any] = field(default_factory=dict)
    no_cost_quotas: List[BillingQuota] = field(default_factory=list)

    @property
    def total_cost(self) -> int:
        total_no_cost_quota = sum(ncq.normalized_amount for ncq in self.no_cost_quotas)
        final_quota = max(self.quota_tb - total_no_cost_quota, 0)
        return int(math.ceil(final_quota)) * int(round(self.cost_per_tb))

    @classmethod
    def parse(
        cls,
        allocation,
        default_quota: int,
        default_cost: int,
    ) -> 'BillingAllocation':
        if quota_attrs := getattr(allocation, QUOTA_ATTRIBUTE_NAME, None):
            quota_raw = quota_attrs[0].value
            float_quota = parse_float(quota_raw, default_quota)
            quota_tb = float_quota if float_quota >= 0 else default_quota
        else:
            quota_tb = default_quota

        cost_per_tb = get_cost_per_tb(allocation, default_cost)

        if (project := getattr(allocation, 'project', None)) is not None:
            project_title = getattr(project, 'title', '-')
            pi = getattr(project, 'pi', None)
            project_extra = {
                'project_title': project_title or '-',
                'pi_name': pi.username if pi else '-',
            }
        else:
            project_extra = {
                'project_title': '-',
                'pi_name': '-',
            }

        storage_resources = getattr(allocation, STORAGE_RESOURCE_ATTRIBUTE_NAME, [])
        resource_name = storage_resources[0].name if storage_resources else '-'

        allotments = getattr(allocation, NO_COST_QUOTA_DATA_ATTRIBUTE_NAME, [])
        no_cost_quotas = [
            BillingQuota.create(allotment.amount, allotment.no_cost_quota.units) for allotment in allotments
        ]

        return cls(
            allocation_id=allocation.id,
            project_id=allocation.project_id,
            quota_tb=quota_tb,
            cost_per_tb=cost_per_tb,
            extra=project_extra
            | {
                'resource_name': resource_name,
                'status': allocation.status.name,
                'end_date': getattr(allocation, 'end_date', None) or '-',
            },
            no_cost_quotas=no_cost_quotas,
        )
