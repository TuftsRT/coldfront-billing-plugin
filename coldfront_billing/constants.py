from decimal import Decimal

import environ
from django.conf import settings

env = environ.Env()

BILLING_ROLE_NAME = "Billing"
MANAGER_ROLE_NAME = "Manager"


# The storage plugin's default for its quota attribute (its QUOTA_ATTRIBUTE_NAME). Repeated here, since
# plugins don't import each other: if storage's default changes, change this too.
STORAGE_PLUGIN_DEFAULT_QUOTA_ATTRIBUTE_NAME = "Storage Quota (TB)"


def default_quota_attribute_name(installed_apps=None) -> str:
    """The allocation attribute billing reads the quota from.

    COLDFRONT_BILLING_QUOTA_ATTRIBUTE_NAME if it's set. Otherwise, with the storage plugin installed, the
    attribute it keeps the quota in, so the two agree without being told: its QUOTA_ATTRIBUTE_NAME, or
    its default. Without it, "quota_in_terabyte". `installed_apps` defaults to settings.INSTALLED_APPS.
    """
    if installed_apps is None:
        installed_apps = settings.INSTALLED_APPS
    # the app, or its AppConfig ("storage.apps.StorageConfig"); not an app whose name only starts with it
    if any(app == "storage" or app.startswith("storage.") for app in installed_apps):
        fallback = env.str("QUOTA_ATTRIBUTE_NAME", STORAGE_PLUGIN_DEFAULT_QUOTA_ATTRIBUTE_NAME)
    else:
        fallback = "quota_in_terabyte"
    return env.str("COLDFRONT_BILLING_QUOTA_ATTRIBUTE_NAME", fallback)


QUOTA_ATTR_NAME = default_quota_attribute_name()
COST_ATTR_NAME = env.str("COLDFRONT_BILLING_COST_ATTRIBUTE_NAME", "cost_per_terabyte")
NO_COST_QUOTA_TYPE_ATTR_NAME = env.str("COLDFRONT_BILLING_NO_COST_QUOTA_TYPE_ATTR_NAME", "no_cost_quota_type")

# Max department/grant rows per project (billing modal + CostCenterSchema)
MAX_COST_CENTER_ASSIGNMENTS = getattr(settings, "COLDFRONT_BILLING_MAX_COST_CENTER_ASSIGNMENTS", 10)

# Attribute names for prefetching
COST_ATTRIBUTE_NAME = "cost_attr"
QUOTA_ATTRIBUTE_NAME = "quota_attr"
BILLING_ATTRIBUTE_NAME = "billing_allocations"
STORAGE_RESOURCE_ATTRIBUTE_NAME = "paid_storage_resource"
ALLOTMENTS_ATTRIBUTE_NAME = "all_allotments"
ALLOCATION_QUOTA_ATTRIBUTE_NAME = "allocation_no_cost_quota"

# Django Q Schedule.name for billing report emails (shared by tasks and scheduling)
BILLING_REPORTS_TOTAL_DEPT_NAME = getattr(settings, "COLDFRONT_BILLING_REPORTS_TOTAL_DEPT_NAME", "C800260")
BILLING_REPORTS_TOTAL_DESCRIPTION = getattr(settings, "COLDFRONT_BILLING_REPORTS_TOTAL_DESCRIPTION", "Storage Charges")
BILLING_SCHEDULE_NAME = "coldfront_billing_report"
BILLING_REPORT_HOUR = getattr(settings, "COLDFRONT_BILLING_REPORT_HOUR", 8)
BILLING_USE_TEST_SCHEDULING = getattr(settings, "COLDFRONT_BILLING_USE_TEST_SCHEDULING", False)

# Defaults for BillingAllocation.parse when quota/cost attributes are missing
DEFAULT_BILLING_QUOTA = Decimal(getattr(settings, "COLDFRONT_BILLING_DEFAULT_QUOTA", 0))
DEFAULT_BILLING_COST = Decimal(getattr(settings, "COLDFRONT_BILLING_DEFAULT_COST", 10))

# Billing account and description settings
BILLING_DEBIT_ACCOUNT_NAME = getattr(settings, "COLDFRONT_BILLING_DEBIT_ACCOUNT_NAME", 1234)
BILLING_CREDIT_ACCOUNT_NAME = getattr(settings, "COLDFRONT_BILLING_CREDIT_ACCOUNT_NAME", 4321)
BILLING_DESCRIPTION_PREFIX = getattr(settings, "COLDFRONT_BILLING_DESCRIPTION_PREFIX", "")
BILLING_IGNORE_DEPTID_PREFIX_LIST = getattr(settings, "COLDFRONT_BILLING_IGNORE_DEPTID_PREFIX_LIST", [])
