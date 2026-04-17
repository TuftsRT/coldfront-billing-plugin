import pytest
from pydantic import ValidationError

from coldfront_billing.schemas import CostCenterSchema


def test_duplicate_department_without_grant_rejected():
    with pytest.raises(ValidationError) as exc_info:
        CostCenterSchema.model_validate(
            {
                'assignments': [
                    {'department': 'DEPT_A', 'percentage': 50},
                    {'department': 'DEPT_A', 'percentage': 50},
                ],
            }
        )
    assert 'Each department and grant combination can only appear once.' in str(exc_info.value)


def test_duplicate_department_grant_pair_rejected():
    with pytest.raises(ValidationError) as exc_info:
        CostCenterSchema.model_validate(
            {
                'assignments': [
                    {'department': 'DEPT_A', 'grant': 'G1', 'percentage': 50},
                    {'department': 'DEPT_A', 'grant': 'G1', 'percentage': 50},
                ],
            }
        )
    assert 'Each department and grant combination can only appear once.' in str(exc_info.value)


def test_same_department_different_grants_allowed():
    schema = CostCenterSchema.model_validate(
        {
            'assignments': [
                {'department': 'DEPT_A', 'grant': 'G1', 'percentage': 50},
                {'department': 'DEPT_A', 'grant': 'G2', 'percentage': 50},
            ],
        }
    )
    assert len(schema.assignments) == 2


def test_equivalent_empty_grant_treated_as_same_pair():
    with pytest.raises(ValidationError):
        CostCenterSchema.model_validate(
            {
                'assignments': [
                    {'department': 'DEPT_A', 'grant': '', 'percentage': 50},
                    {'department': 'DEPT_A', 'percentage': 50},
                ],
            }
        )


def test_percentages_must_sum_to_100_single_row():
    schema = CostCenterSchema.model_validate(
        {'assignments': [{'department': 'DEPT_A', 'percentage': 100}]},
    )
    assert schema.assignments[0].percentage == 100


def test_percentages_must_sum_to_100_multiple_rows():
    schema = CostCenterSchema.model_validate(
        {
            'assignments': [
                {'department': 'DEPT_A', 'percentage': 60},
                {'department': 'DEPT_B', 'percentage': 40},
            ],
        },
    )
    assert sum(a.percentage for a in schema.assignments) == 100


def test_percentages_under_100_rejected():
    with pytest.raises(ValidationError) as exc_info:
        CostCenterSchema.model_validate(
            {
                'assignments': [
                    {'department': 'DEPT_A', 'percentage': 50},
                    {'department': 'DEPT_B', 'percentage': 40},
                ],
            },
        )
    assert 'Percentages must sum to 100, got 90' in str(exc_info.value)


def test_percentages_over_100_rejected():
    with pytest.raises(ValidationError) as exc_info:
        CostCenterSchema.model_validate(
            {
                'assignments': [
                    {'department': 'DEPT_A', 'percentage': 60},
                    {'department': 'DEPT_B', 'percentage': 50},
                ],
            },
        )
    assert 'Percentages must sum to 100, got 110' in str(exc_info.value)
