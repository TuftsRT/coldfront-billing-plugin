from django.http import HttpRequest

from coldfront_billing.prefetch import has_billing_perm


def billing_role(request: HttpRequest):
    user = request.user
    
    if not user.is_authenticated:
        return {}

    return {'has_billing_role': user.is_superuser or has_billing_perm(user)}
