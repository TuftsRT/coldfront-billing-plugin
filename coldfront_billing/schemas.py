from typing import List, Optional, Tuple

from pydantic import BaseModel, Field, model_validator


class AssignmentSchema(BaseModel):
    department: str = Field(..., description='Department name')
    grant: Optional[str] = Field(default=None, description='Grant name')
    percentage: int = Field(..., ge=0, le=100, description='Percentage of the allocation')


class CostCenterSchema(BaseModel):
    assignments: List[AssignmentSchema] = Field(
        ...,
        min_length=1,
        max_length=4,
        description='Cost center assignments: department, optional grant, and percentage per entry',
    )

    @model_validator(mode='after')
    def validate_unique_department_grant_pairs(self):
        seen_pairs: set[Tuple[str, str]] = set()
        for assignment in self.assignments:
            dept = assignment.department.strip()
            grant = (assignment.grant or '').strip()
            if (dept, grant) in seen_pairs:
                raise ValueError('Each department and grant combination can only appear once.')
            seen_pairs.add((dept, grant))
        return self

    @model_validator(mode='after')
    def validate_percentages_sum_to_100(self):
        total = sum(a.percentage for a in self.assignments)
        if total != 100:
            raise ValueError(f'Percentages must sum to 100, got {total}')
        return self
