from pydantic import BaseModel
from typing import List, Optional

class ValidateConfigRequest(BaseModel):
    commands: str
    deviceType: str = "Cisco"

class ValidateConfigResponse(BaseModel):
    validationLogs: List[dict]
    simulationLogs: List[str]
    destructiveAlerts: List[str]
    hasError: bool
    hasWarning: bool
    requiresDualApproval: bool

class DeployConfigRequest(BaseModel):
    commands: str
    device: str = "router-hq"
    simulateFailure: bool = False
    managerApproved: bool = False
    adminApproved: bool = False

class DeployConfigResponse(BaseModel):
    success: bool
    backupId: str
    backupLogs: str
    deployLogs: str
    verificationLogs: str
    rollbackExecuted: bool
    rollbackLogs: str
