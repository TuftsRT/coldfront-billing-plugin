import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from coldfront_billing.constants import COST_ATTRIBUTE_NAME, QUOTA_ATTRIBUTE_NAME, STORAGE_RESOURCE_ATTRIBUTE_NAME


def _first_or_none(sequence):
    return sequence[0] if sequence else None


def _parse_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass
class BillingAllocation:
    allocation_id: int
    project_id: int
    quota_tb: int | float
    cost_per_tb: int | float
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_cost(self) -> int:
        return int(math.ceil(self.quota_tb)) * int(round(self.cost_per_tb))

    @classmethod
    def parse(
        cls,
        allocation,
        default_quota: int,
        default_cost: int,
    ) -> 'BillingAllocation':
        if quota_attrs := getattr(allocation, QUOTA_ATTRIBUTE_NAME, None):
            quota_raw = quota_attrs[0].value
            float_quota = _parse_float(quota_raw, default_quota)
            quota_tb = float_quota if float_quota >= 0 else default_quota
        else:
            quota_tb = default_quota

        storage_resource = _first_or_none(getattr(allocation, STORAGE_RESOURCE_ATTRIBUTE_NAME, []))

        if storage_resource and (cost_attrs := getattr(storage_resource, COST_ATTRIBUTE_NAME, None)):
            float_cost = _parse_float(cost_attrs[0].value, default_cost)
            cost_per_tb = float_cost if float_cost >= 0 else default_cost
        else:
            cost_per_tb = default_cost
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
        )


@dataclass
class ApiErrorResponseDTO:
    success: bool = False
    error: Optional[str] = None
    errors: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {'success': self.success}
        if self.error:
            result['error'] = self.error
        if self.errors:
            result['errors'] = self.errors
        return result


@dataclass
class ApiSuccessResponseDTO:
    success: bool = True
    message: Optional[str] = None
    assignments: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {'success': self.success}
        if self.message:
            result['message'] = self.message
        if self.assignments:
            result['assignments'] = self.assignments
        return result
