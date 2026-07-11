from decimal import Decimal

import environ
from django.conf import settings

env = environ.Env()

BILLING_ROLE_NAME = 'Billing'
MANAGER_ROLE_NAME = 'Manager'

QUOTA_ATTR_NAME = env.str('COLDFRONT_BILLING_QUOTA_ATTRIBUTE_NAME', 'quota_in_terabyte')
COST_ATTR_NAME = env.str('COLDFRONT_BILLING_COST_ATTRIBUTE_NAME', 'cost_per_terabyte')
NO_COST_QUOTA_TYPE_ATTR_NAME = env.str('COLDFRONT_BILLING_NO_COST_QUOTA_TYPE_ATTR_NAME', 'no_cost_quota_type')

# Max department/grant rows per project (billing modal + CostCenterSchema)
MAX_COST_CENTER_ASSIGNMENTS = getattr(settings, 'COLDFRONT_BILLING_MAX_COST_CENTER_ASSIGNMENTS', 10)

# Attribute names for prefetching
COST_ATTRIBUTE_NAME = 'cost_attr'
QUOTA_ATTRIBUTE_NAME = 'quota_attr'
BILLING_ATTRIBUTE_NAME = 'billing_allocations'
STORAGE_RESOURCE_ATTRIBUTE_NAME = 'paid_storage_resource'
ALLOTMENTS_ATTRIBUTE_NAME = 'all_allotments'
ALLOCATION_QUOTA_ATTRIBUTE_NAME = 'allocation_no_cost_quota'

# Django Q Schedule.name for billing report emails (shared by tasks and scheduling)
BILLIG_REPORTS_TOTAL_DEPT_NAME = getattr(settings, 'COLDFRONT_BILLIG_REPORTS_TOTAL_DEPT_NAME', 'C800260')
BILLIG_REPORTS_TOTAL_DESCRIPTION = getattr(settings, 'COLDFRONT_BILLIG_REPORTS_TOTAL_DESCRIPTION', 'Storage Charges')
BILLING_SCHEDULE_NAME = 'coldfront_billing_report'
BILLING_REPORT_HOUR = getattr(settings, 'COLDFRONT_BILLING_REPORT_HOUR', 8)
BILLING_USE_TEST_SCHEDULING = getattr(settings, 'COLDFRONT_BILLING_USE_TEST_SCHEDULING', False)

# Defaults for BillingAllocation.parse when quota/cost attributes are missing
DEFAULT_BILLING_QUOTA = Decimal(getattr(settings, 'COLDFRONT_BILLING_DEFAULT_QUOTA', 0))
DEFAULT_BILLING_COST = Decimal(getattr(settings, 'COLDFRONT_BILLING_DEFAULT_COST', 10))
