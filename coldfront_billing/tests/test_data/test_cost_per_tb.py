"""parse_cost_per_tb: the one rule for reading a resource's cost per TB, used by billing and the estimate."""

from decimal import Decimal

import pytest

from coldfront_billing.data.common import parse_cost_per_tb

DEFAULT = Decimal("10")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("12.5", Decimal("12.5")),
        ("0", Decimal("0")),
        (None, DEFAULT),  # no attribute value
        ("", DEFAULT),
        ("abc", DEFAULT),
        ("-1", DEFAULT),
        ("nan", DEFAULT),
    ],
)
def test_a_missing_unparseable_or_negative_cost_is_the_default(value, expected):
    assert parse_cost_per_tb(value, DEFAULT) == expected
