from typing import Dict

from pydantic import BaseModel, Field, field_validator


class CostCenterSchema(BaseModel):
    assignments: Dict[str, int] = Field(
        ...,
        min_length=1,
        max_length=4,
        description='Cost center assignments as dict with cost center names as keys and percentages as values',
    )

    @field_validator('assignments')
    @classmethod
    def validate_percentage_values(cls, value: Dict[str, int]) -> Dict[str, int]:
        """Ensure that all percentage values are valid (0-100)."""
        for cost_center, percentage in value.items():
            if not isinstance(percentage, int) or percentage < 0 or percentage > 100:
                raise ValueError(f'Percentage for {cost_center} must be an integer between 0 and 100, got {percentage}')
        return value

    @field_validator('assignments')
    @classmethod
    def validate_percentages_sum_to_100(cls, value: Dict[str, int]) -> Dict[str, int]:
        """Ensure that all percentages sum to exactly 100."""
        total = sum(value.values())
        if total != 100:
            raise ValueError(f'Percentages must sum to 100, got {total}')
        return value
