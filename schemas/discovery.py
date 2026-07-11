from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class DiscoveryRunRequest(BaseModel):
    subnet: str = "10.0.1.0/24"

class DiscoveryScheduleRequest(BaseModel):
    subnet: str = "10.0.1.0/24"
    intervalMinutes: int = 60

class DiscoveryLogResponse(BaseModel):
    id: int
    timestamp: datetime
    subnet: str
    status: str
    devices_found: int
    log_output: Optional[str] = None

    class Config:
        from_attributes = True
