from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AuditLogSchema(BaseModel):
    id: int
    timestamp: datetime
    user_name: str
    user: Optional[str] = None  # Frontend compatibility mapping
    role: str
    ip: str
    action: str
    details: str
    status: str
    changes: Optional[str] = None
    approvals: Optional[str] = None
    rollback: Optional[str] = None

    class Config:
        from_attributes = True
