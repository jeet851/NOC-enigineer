from pydantic import BaseModel
from typing import List, Optional

class CredentialTestRequest(BaseModel):
    name: str
    device: str = "router-hq"

class CredentialTestResponse(BaseModel):
    success: bool
    message: str
    logs: str

class CredentialValidationResponse(BaseModel):
    valid: bool
    errors: List[str]
