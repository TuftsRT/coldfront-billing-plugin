import environ

env = environ.Env()


quota_attr_name = env.str('COLDFRONT_BILLING_QUOTA_ATTRIBUTE_NAME', 'quota_in_terabyte')
cost_attr_name = env.str('COLDFRONT_BILLING_COST_ATTRIBUTE_NAME', 'cost_per_terabyte')
