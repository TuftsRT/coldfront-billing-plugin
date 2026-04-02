"""Unit tests for no-cost quota allotment helpers (parse_allocations)."""

import pytest

from coldfront_billing.data.quota import AllocationAssignement, parse_allocations


class TestParseAllocations:
    """Tests for parse_allocations (bulk auto-assign POST parsing)."""

    def test_empty_allocation_ids_raises(self):
        with pytest.raises(Exception, match='No allocations provided'):
            parse_allocations([], ['1'])

    def test_empty_amount_strs_raises(self):
        with pytest.raises(Exception, match='No amounts provided'):
            parse_allocations(['1'], [])

    def test_mismatched_lengths_raises(self):
        with pytest.raises(Exception, match='counts do not match'):
            parse_allocations(['1', '2'], ['1.0'])

    def test_blank_allocation_id_raises(self):
        with pytest.raises(Exception, match='missing allocation'):
            parse_allocations(['1', ''], ['1.0', '2.0'])

    def test_invalid_allocation_id_raises(self):
        with pytest.raises(Exception, match='allocation id is invalid'):
            parse_allocations(['1', 'not-int'], ['1.0', '2.0'])

    def test_invalid_amount_raises(self):
        with pytest.raises(Exception, match='amount of allocation is invalid'):
            parse_allocations(['1'], ['not-a-float'])

    def test_comma_as_decimal_separator(self):
        result = parse_allocations(['10'], ['1,5'])
        assert result == [AllocationAssignement(10, 1.5)]

    def test_strips_whitespace(self):
        result = parse_allocations(['  7  '], ['  2.5  '])
        assert result == [AllocationAssignement(7, 2.5)]

    def test_multiple_rows(self):
        result = parse_allocations(['1', '2', '3'], ['1.0', '2,5', '0'])
        assert result == [
            AllocationAssignement(1, 1.0),
            AllocationAssignement(2, 2.5),
            AllocationAssignement(3, 0.0),
        ]
