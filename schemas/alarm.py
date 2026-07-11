from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AlarmSchema(BaseModel):
    id: str
    timestamp: datetime
    source: str
    metric: str
    value: str
    severity: str
    time_display: str
    status: str

    class Config:
        from_attributes = True
