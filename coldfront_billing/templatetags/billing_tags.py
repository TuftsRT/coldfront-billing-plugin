from django import template

from coldfront_billing.constants import QUOTA_ATTR_NAME

register = template.Library()


@register.simple_tag
def billing_quota_attr_name():
    return QUOTA_ATTR_NAME
