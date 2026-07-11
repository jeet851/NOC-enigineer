from typing import Optional, Any, Dict
from pydantic import BaseModel

class StandardResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    pagination: Optional[Dict[str, Any]] = None

def make_success_response(data: Any, pagination: Optional[Dict[str, Any]] = None) -> dict:
    return {
        "success": True,
        "data": data,
        "pagination": pagination
    }

def make_error_response(message: str, code: str = "INTERNAL_SERVER_ERROR", details: Optional[Any] = None) -> dict:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details
        }
    }
