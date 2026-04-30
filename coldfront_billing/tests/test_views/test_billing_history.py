"""Tests for BillingScheduleHistoryListView (reports billing history)."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from coldfront_billing.models import BillingScheduleHistory
from coldfront_billing.views.reports.history import BillingScheduleHistoryListView


def _history_url():
    return reverse('reports_billing_history')


def _make_history_row(
    *,
    started=None,
    stopped=None,
    status=BillingScheduleHistory.Status.SUCCESS,
    details='',
):
    if started is None:
        started = timezone.now() - timedelta(hours=1)
    return BillingScheduleHistory.objects.create(
        started=started,
        stopped=stopped,
        status=status,
        details=details,
    )


@pytest.mark.django_db
@pytest.mark.usefixtures('configure_urls')
class TestBillingScheduleHistoryListView:
    """Test suite for BillingScheduleHistoryListView."""

    @staticmethod
    def _get(client, user, **query):
        client.force_login(user)
        return client.get(_history_url(), query or {})

    def test_unauthenticated_user_redirected(self, client):
        response = client.get(_history_url())
        assert response.status_code == 302
        assert '/login' in response.url

    def test_non_superuser_forbidden(self, client, user):
        response = self._get(client, user)
        assert response.status_code == 403

    def test_superuser_empty_list(self, client, superuser):
        response = self._get(client, superuser)
        assert response.status_code == 200
        assert list(response.context['history_rows']) == []
        assert response.context['execution_date_from'] == ''
        assert response.context['execution_date_to'] == ''
        assert response.context['failed_only'] is False
        assert response.context['history_filters_active'] is False

    def test_superuser_sees_rows(self, client, superuser):
        a = _make_history_row(details='run-a')
        b = _make_history_row(details='run-b')
        response = self._get(client, superuser)
        assert response.status_code == 200
        ids = [r.id for r in response.context['history_rows']]
        assert set(ids) == {a.id, b.id}

    def test_context_pagination_params(self, client, superuser):
        _make_history_row()
        response = self._get(client, superuser, execution_date_from='2020-01-01', order_by='id', direction='asc')
        assert response.status_code == 200
        assert 'all_params' in response.context
        assert 'filter_parameters' in response.context
        assert 'page' not in response.context['all_params']
        assert 'execution_date_from=2020-01-01' in response.context['all_params']
        assert 'order_by=id' in response.context['all_params']
        assert 'direction=asc' in response.context['all_params']
        assert 'order_by' not in response.context['filter_parameters']
        assert 'execution_date_from=2020-01-01' in response.context['filter_parameters']

    def test_filter_execution_date_range(self, client, superuser):
        tz = timezone.get_current_timezone()
        inside = timezone.make_aware(datetime(2024, 6, 10, 12, 0, 0), tz)
        before = timezone.make_aware(datetime(2024, 5, 1, 12, 0, 0), tz)
        after = timezone.make_aware(datetime(2024, 7, 1, 12, 0, 0), tz)
        row_in = _make_history_row(stopped=inside)
        _make_history_row(stopped=before)
        _make_history_row(stopped=after)
        response = self._get(
            client,
            superuser,
            execution_date_from='2024-06-01',
            execution_date_to='2024-06-30',
        )
        assert response.status_code == 200
        ids = [r.id for r in response.context['history_rows']]
        assert ids == [row_in.id]

    def test_filter_failed_only_excludes_success(self, client, superuser):
        ok = _make_history_row(status=BillingScheduleHistory.Status.SUCCESS)
        bad = _make_history_row(status=BillingScheduleHistory.Status.FAILED_MAIL)
        response = self._get(client, superuser, failed_only='1')
        assert response.status_code == 200
        ids = [r.id for r in response.context['history_rows']]
        assert ok.id not in ids
        assert bad.id in ids
        assert response.context['failed_only'] is True
        assert response.context['history_filters_active'] is True

    def test_sort_order_by_id_asc(self, client, superuser):
        _make_history_row()
        _make_history_row()
        response = self._get(client, superuser, order_by='id', direction='asc')
        ids = [r.id for r in response.context['history_rows']]
        assert ids == sorted(ids)

    def test_sort_order_by_id_desc(self, client, superuser):
        _make_history_row()
        _make_history_row()
        response = self._get(client, superuser, order_by='id', direction='des')
        ids = [r.id for r in response.context['history_rows']]
        assert ids == sorted(ids, reverse=True)

    def test_invalid_order_by_uses_default_ordering(self, client, superuser):
        old = _make_history_row()
        new = _make_history_row()
        response = self._get(client, superuser, order_by='not_a_column', direction='asc')
        assert response.status_code == 200
        ids = [r.id for r in response.context['history_rows']]
        assert set(ids) == {old.id, new.id}

    def test_pagination_second_page(self, client, superuser):
        """Paginate with 2 per page; COLDFRONT_BILLING_PAGINATE_BY is read at mixins import so patch the view."""
        for _ in range(3):
            _make_history_row()
        with patch.object(BillingScheduleHistoryListView, 'paginate_by', 2):
            response = self._get(client, superuser, page='2')
        assert response.status_code == 200
        assert len(response.context['history_rows']) == 1
        assert response.context['page_obj'].number == 2
