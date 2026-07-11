from pydantic import BaseModel
from typing import Optional

class SettingsRequest(BaseModel):
    interval: Optional[int] = None
    healingPolicy: Optional[str] = None
    severityThreshold: Optional[int] = None

class SettingsResponse(BaseModel):
    interval: int
    healingPolicy: str
    severityThreshold: int
