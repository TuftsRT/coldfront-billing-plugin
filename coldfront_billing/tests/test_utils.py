"""Unit tests for coldfront_billing.utils."""

from datetime import date

import pytest
from django.utils import timezone

from coldfront_billing.utils import (
    calculate_next_run,
    first_or_none,
    get_month_abbr,
    parse_float,
    validate_emails,
)


class TestParseFloat:
    def test_valid_float(self):
        assert parse_float('3.5', 0) == 3.5

    def test_invalid_returns_default(self):
        assert parse_float('x', 7) == 7


class TestFirstOrNone:
    def test_empty_sequence(self):
        assert first_or_none([]) is None

    def test_returns_first(self):
        assert first_or_none([1, 2]) == 1


class TestValidateEmails:
    def test_splits_semicolon_and_comma_separated(self):
        valid, invalid = validate_emails('alice@tufts.com; bob@tufts.com, carol@tufts.com')
        assert invalid == []
        assert valid == ['alice@tufts.com', 'bob@tufts.com', 'carol@tufts.com']

    def test_invalid_addresses_collected(self):
        valid, invalid = validate_emails('good@tufts.com, not-an-email')
        assert 'good@tufts.com' in valid
        assert 'not-an-email' in invalid

    def test_deduplicates_normalized_addresses(self):
        valid, invalid = validate_emails('a@tufts.com; a@tufts.com')
        assert valid == ['a@tufts.com']
        assert invalid == []


class TestCalculateNextRun:
    def test_requires_hour_or_minutes(self):
        with pytest.raises(ValueError, match='Either hour or minutes'):
            calculate_next_run(date.today())

    def test_monthly_from_start_date(self):
        start = date(2030, 6, 15)
        result = calculate_next_run(start, hour=9)
        assert timezone.is_aware(result)
        assert result.hour == 9
        assert result.minute == 0


class TestGetMonthAbbr:
    def test_returns_uppercase_three_letter_month(self):
        abbr = get_month_abbr()
        assert len(abbr) == 3
        assert abbr.isupper()
