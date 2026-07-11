from pydantic import BaseModel
from typing import List, Optional

class TelemetryMetricsSchema(BaseModel):
    cpu: int
    ram: int
    disk: int
    network: int
    sla: float

class TelemetryNodeSchema(BaseModel):
    name: str
    status: str
    message: Optional[str] = None
    cpu: int
    ram: int

class TelemetryAlarmSchema(BaseModel):
    id: str
    source: str
    metric: str
    value: str
    severity: str
    time: str

class TelemetryResponse(BaseModel):
    metrics: TelemetryMetricsSchema
    nodes: List[TelemetryNodeSchema]
    alarms: List[TelemetryAlarmSchema]
    geminiActive: bool
    slackActive: bool
