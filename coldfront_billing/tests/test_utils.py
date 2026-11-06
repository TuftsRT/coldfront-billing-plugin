"""Unit tests for coldfront_billing.utils."""

from datetime import date

import pytest
from django.utils import timezone

from coldfront_billing.utils import (
    calculate_next_run,
    elide_middle,
    first_or_none,
    get_month_abbr,
    parse_float,
    sanitize_csv_value,
    validate_emails,
)


class TestParseFloat:
    def test_valid_float(self):
        assert parse_float("3.5", 0) == 3.5

    def test_invalid_returns_default(self):
        assert parse_float("x", 7) == 7


class TestFirstOrNone:
    def test_empty_sequence(self):
        assert first_or_none([]) is None

    def test_returns_first(self):
        assert first_or_none([1, 2]) == 1


class TestValidateEmails:
    def test_splits_semicolon_and_comma_separated(self):
        valid, invalid = validate_emails("alice@tufts.com; bob@tufts.com, carol@tufts.com")
        assert invalid == []
        assert valid == ["alice@tufts.com", "bob@tufts.com", "carol@tufts.com"]

    def test_invalid_addresses_collected(self):
        valid, invalid = validate_emails("good@tufts.com, not-an-email")
        assert "good@tufts.com" in valid
        assert "not-an-email" in invalid

    def test_deduplicates_normalized_addresses(self):
        valid, invalid = validate_emails("a@tufts.com; a@tufts.com")
        assert valid == ["a@tufts.com"]
        assert invalid == []


class TestCalculateNextRun:
    def test_requires_hour_or_minutes(self):
        with pytest.raises(ValueError, match="Either hour or minutes"):
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


class TestElide:
    def test_elide_middle(self):
        assert elide_middle("abcdef", 5) == "a...f"
        assert elide_middle("abcdef", 6) == "abcdef"
        assert elide_middle("abcdef", 7) == "abcdef"
        assert elide_middle("abcdefghijklmnopqrst", 8) == "abc...st"
        with pytest.raises(ValueError):
            elide_middle("abcdef", 3)
        with pytest.raises(ValueError):
            elide_middle("abcdef", 4)


class TestSanitizeCsvValue:
    def test_plain_value_is_unchanged(self):
        assert sanitize_csv_value("plain value") == "plain value"

    def test_strips_surrounding_whitespace(self):
        assert sanitize_csv_value("  spaced  ") == "spaced"

    @pytest.mark.parametrize(
        "value, expected",
        [
            (123, "123"),
            (3.14, "3.14"),
            (None, "None"),
        ],
    )
    def test_non_string_values_are_coerced_to_string(self, value, expected):
        assert sanitize_csv_value(value) == expected

    def test_empty_string_is_unchanged(self):
        assert sanitize_csv_value("") == ""

    def test_whitespace_only_string_becomes_empty(self):
        assert sanitize_csv_value("   ") == ""

    @pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "|"])
    def test_dangerous_leading_character_is_neutralized_with_a_quote_prefix(self, prefix):
        """Excel/Sheets/LibreOffice treat a leading =, +, -, @, or | as the start
        of a formula; prefixing with a straight quote forces text interpretation."""
        value = f"{prefix}cmd|calc"
        assert sanitize_csv_value(value) == f"'{prefix}cmd|calc"

    @pytest.mark.parametrize(
        "payload",
        [
            "=SUM(A1:A2)",
            '=cmd|" /C calc"!A0',
            "+1+1",
            "-2+3",
            "@SUM(1+1)",
            "|calc",
            '=HYPERLINK("http://evil.example","click me")',
        ],
    )
    def test_common_csv_injection_payloads_no_longer_start_with_a_dangerous_character(self, payload):
        result = sanitize_csv_value(payload)
        assert not result.lstrip('"').startswith(("=", "+", "-", "@", "|"))

    def test_dangerous_character_not_at_start_is_left_alone(self):
        assert sanitize_csv_value("a=b+c-d@e|f") == "a=b+c-d@e|f"

    def test_only_the_leading_character_triggers_escaping_once(self):
        # every character in the danger list appears, but only the leading '='
        # should result in a single quote prefix being added
        assert sanitize_csv_value("=+-@|") == "'=+-@|"

    def test_value_with_comma_is_wrapped_in_quotes(self):
        assert sanitize_csv_value("value,with,comma") == '"value,with,comma"'

    def test_value_with_double_quote_is_wrapped_and_quotes_doubled(self):
        assert sanitize_csv_value('value"with"quote') == '"value""with""quote"'

    def test_value_without_comma_or_quote_is_not_wrapped(self):
        assert sanitize_csv_value("no special characters here") == "no special characters here"

    def test_formula_prefix_combined_with_comma_is_both_escaped_and_quoted(self):
        assert sanitize_csv_value("=1,2") == '"\'=1,2"'

    def test_formula_prefix_combined_with_embedded_quote_is_both_escaped_and_quoted(self):
        assert sanitize_csv_value('=cmd|" /C calc"!A0') == '"\'=cmd|"" /C calc""!A0"'
