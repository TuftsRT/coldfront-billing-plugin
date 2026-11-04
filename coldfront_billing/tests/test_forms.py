"""Unit tests for coldfront_billing forms."""

import pytest

from coldfront_billing.forms.allocation import AllocationDetailsForm


@pytest.mark.django_db
class TestAllocationDetailsFormQuota:
    @pytest.mark.parametrize('quota', ['0.1', '0.2', '10'])
    def test_accepts_the_minimum_and_above(self, quota):
        """0.1 is the stated minimum; a float bound would reject it, since Decimal('0.1') < 0.1."""
        form = AllocationDetailsForm(data={'quota_in_terabyte': quota})
        assert 'quota_in_terabyte' not in form.errors

    def test_rejects_below_the_minimum(self):
        form = AllocationDetailsForm(data={'quota_in_terabyte': '0.09'})
        assert 'quota_in_terabyte' in form.errors
