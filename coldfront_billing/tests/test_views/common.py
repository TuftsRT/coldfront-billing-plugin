from urllib.parse import urlencode

from django.urls import reverse


def get_billing_response(client, user, query_params=''):
    """Helper to get billing view response."""
    client.force_login(user)
    url = reverse('billing_index') + query_params
    return client.get(url)


def post_delete_allotment(client, user, allotment_id):
    """Helper to POST delete allotment."""
    client.force_login(user)
    return client.post(
        reverse('no_cost_quota_manage_allotment'),
        data={
            'action': 'delete',
            'allotment_id': allotment_id,
        },
    )


def _get_manage_response(client, user):
    """Helper to GET the manage no cost quota page."""
    client.force_login(user)
    return client.get(reverse('manage_no_cost_quota'))


def get_assign_response(client, user, selected_quota):
    """Helper to GET the assign no cost quota page."""
    client.force_login(user)
    url = f'{reverse("assign_no_cost_quota")}?selected_quota={selected_quota}'
    return client.get(url)


def post_create_allotment(client, user, quota_id, allocation_id, amount):
    """Helper to POST create allotment."""
    client.force_login(user)
    return client.post(
        reverse('no_cost_quota_manage_allotment'),
        data={
            'quota_id': quota_id,
            'allocation_id': allocation_id,
            'amount_tb': amount,
        },
    )


def post_auto_assign_allotments(client, user, quota_id, allocation_amount_pairs):
    """Helper to POST bulk auto-assign (interleaved allocation_id / amount like assign.html)."""
    client.force_login(user)
    pairs = [('quota_id', str(quota_id))]
    for allocation_id, amount in allocation_amount_pairs:
        pairs.append(('allocation_id', str(allocation_id)))
        pairs.append(('amount', str(amount)))
    body = urlencode(pairs)
    return client.post(
        reverse('no_cost_quota_auto_allotment'),
        data=body,
        content_type='application/x-www-form-urlencoded',
    )
