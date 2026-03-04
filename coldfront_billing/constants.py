import environ

env = environ.Env()


QUOTA_ATTR_NAME = env.str('COLDFRONT_BILLING_QUOTA_ATTRIBUTE_NAME', 'quota_in_terabyte')
COST_ATTR_NAME = env.str('COLDFRONT_BILLING_COST_ATTRIBUTE_NAME', 'cost_per_terabyte')
NO_COST_QUOTA_TYPE_ATTR_NAME = env.str('COLDFRONT_BILLING_NO_COST_QUOTA_TYPE_ATTR_NAME', 'no_cost_quota_type')

# Attribute names for prefetching
COST_ATTRIBUTE_NAME = 'cost_attr'
QUOTA_ATTRIBUTE_NAME = 'quota_attr'
BILLING_ATTRIBUTE_NAME = 'billing_allocations'
STORAGE_RESOURCE_ATTRIBUTE_NAME = 'paid_storage_resource'
NO_COST_QUOTA_DATA_ATTRIBUTE_NAME = 'no_cost_quota_data'
