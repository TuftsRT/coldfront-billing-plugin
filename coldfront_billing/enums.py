from enum import Enum


class ProjectStatus(str, Enum):
    ACTIVE = "Active"
    ARCHIVED = "Archived"
    NEW = "New"


class AllocationStatus(str, Enum):
    ACTIVE = "Active"
    REJECTED = "Rejected"


class StorageUnit(str, Enum):
    TB = "TB"
    GB = "GB"

    @staticmethod
    def parse(units: str) -> "StorageUnit":
        try:
            return StorageUnit(units)
        except ValueError:
            return StorageUnit.TB
