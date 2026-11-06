from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ApiErrorResponseDTO:
    success: bool = False
    error: Optional[str] = None
    errors: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {"success": self.success}
        if self.error:
            result["error"] = self.error
        if self.errors:
            result["errors"] = self.errors
        return result


@dataclass
class ApiSuccessResponseDTO:
    success: bool = True
    message: Optional[str] = None
    assignments: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {"success": self.success}
        if self.message:
            result["message"] = self.message
        if self.assignments is not None:
            result["assignments"] = self.assignments
        return result
