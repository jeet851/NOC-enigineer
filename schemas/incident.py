from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class IncidentResponse(BaseModel):
    id: str
    timestamp: datetime
    severity: str
    device_name: str
    site: str
    vendor: str
    description: str
    business_impact: str
    confidence: str
    root_cause: str
    status: str
    
    # Optional Enriched AI Fields
    evidence: Optional[str] = None
    remediation_commands: Optional[str] = None
    verification_steps: Optional[str] = None
    rollback_plan: Optional[str] = None
    risk_level: Optional[str] = None
    repair_time: Optional[str] = None
    engineering_report: Optional[str] = None

    class Config:
        from_attributes = True
