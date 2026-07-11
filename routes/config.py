from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, Optional, List

from api.deps import get_db, get_current_user
from schemas.config import ValidateConfigRequest, ValidateConfigResponse, DeployConfigRequest, DeployConfigResponse
from services.audit import AuditService
from services.alarm import AlarmService
from automation.device_automation import DeviceAutomationManager
from services.config_manager import ConfigManagerService
import ai_engine
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["configuration"])

from services.redis_cache import RedisCacheManager
import json

class RedisDict(dict):
    def __init__(self, name, defaults):
        self.name = name
        self.defaults = defaults
    def _get_data(self):
        val = RedisCacheManager.get(self.name)
        if val:
            try:
                return json.loads(val)
            except Exception:
                pass
        # Initialize default state in Redis if empty
        data = self.defaults.copy()
        RedisCacheManager.set(self.name, json.dumps(data))
        return data
    def _set_data(self, data):
        RedisCacheManager.set(self.name, json.dumps(data))
    def get(self, key, default=None):
        return self._get_data().get(key, default)
    def __getitem__(self, key):
        return self._get_data()[key]
    def __setitem__(self, key, value):
        data = self._get_data()
        data[key] = value
        self._set_data(data)
    def __contains__(self, key):
        return key in self._get_data()
    def update(self, *args, **kwargs):
        data = self._get_data()
        data.update(*args, **kwargs)
        self._set_data(data)

active_scenarios_state = RedisDict("active_scenarios_state", {
    "vpn_is_down": True,
    "server_cpu_100": True,
    "log_partition_94": True,
    "ssh_spray_attack": True
})

@router.post("/validate-config", response_model=ValidateConfigResponse)
async def api_validate_config(req: ValidateConfigRequest, user: dict = Depends(get_current_user)):
    commands = req.commands.strip()
    device_type = req.deviceType
    
    if not commands:
        raise HTTPException(status_code=400, detail="No configuration content to validate.")
        
    validation_logs, has_error = ai_engine.validate_commands(commands, device_type)
    simulation_logs, has_warning = ai_engine.run_simulation(commands, device_type)
    destructive_alerts = ai_engine.check_ai_safety(commands)
    
    return {
        "validationLogs": validation_logs,
        "simulationLogs": simulation_logs,
        "destructiveAlerts": destructive_alerts,
        "hasError": has_error,
        "hasWarning": has_warning,
        "requiresDualApproval": len(destructive_alerts) > 0
    }

@router.post("/deploy-config", response_model=DeployConfigResponse)
async def api_deploy_config(req: DeployConfigRequest, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    username = user["username"]
    role = user["role"]
    
    commands = req.commands.strip()
    device = req.device
    simulate_failure = req.simulateFailure
    
    if not commands:
        raise HTTPException(status_code=400, detail="No configuration provided.")
        
    # Enforce Zero-Trust RBAC checks
    if role == "Read Only":
        AuditService.log_audit_event(
            db=db,
            user_name=username,
            role=role,
            action="Deployment Blocked",
            ip="127.0.0.1",
            details=f"Read-only access blocked from modifying configuration on {device}.",
            status="Blocked"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission Denied: Read-only users cannot modify configurations."
        )
        
    if role == "Engineer" and requires_dual:
        AuditService.log_audit_event(
            db=db,
            user_name=username,
            role=role,
            action="Deployment Blocked",
            ip="127.0.0.1",
            details=f"Engineer unauthorized for direct deployment of destructive patches on {device}.",
            status="Blocked"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission Denied: Engineers cannot deploy destructive patches directly. Escalated for Operator/Admin approvals."
        )
        
    destructive_alerts = ai_engine.check_ai_safety(commands)
    requires_dual = len(destructive_alerts) > 0
    
    manager_approved = req.managerApproved
    admin_approved = req.adminApproved
    
    # Dual approval requirement check
    if requires_dual:
        if not (manager_approved and admin_approved):
            AuditService.log_audit_event(
                db=db,
                user_name=username,
                role=role,
                action="Dual Approval Rejected",
                ip="127.0.0.1",
                details=f"Destructive command deployment blocked on {device} (Dual Approval required).",
                status="Blocked"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Destructive configurations require DUAL approvals (Operator + Admin)."
            )
            
    # Engineer normal change Operator approval check
    if role == "Engineer" and not manager_approved and not requires_dual:
        AuditService.log_audit_event(
            db=db,
            user_name=username,
            role=role,
            action="Operator Approval Missing",
            ip="127.0.0.1",
            details=f"Engineer blocked from deploying on {device} without Operator verification token.",
            status="Blocked"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Deployment blocked. Engineers require Operator authorization."
        )

        
    # Execute configuration patch deployment:
    backup_id = f"CFG_BCK_{device.upper()}_{int(datetime.now().timestamp())}"
    backup_logs = f"! State Backup of {device} created successfully.\nshow running-config\n! Backup ID: {backup_id}"
    
    deploy_logs = [
        f"Connecting to device {device} over secure SSHv2 connection...",
        f"Verifying vendor device keys against encrypted Vault profile...",
        "Device authenticated using vaulted credentials. Session established.",
        "Capturing running configuration backup...",
        f"Saved backup configuration to storage reference {backup_id}.",
        f"Deploying configuration patch commands:\n{commands}",
        "Applying commands... Configuration synced.",
        "Executing write memory update to startup-config..."
    ]
    
    verification_passed = not (simulate_failure or "fail" in commands.lower())
    verification_logs = [
        "Starting automated post-outage verification sweep...",
        f"Testing ping loop on interfaces of {device} -> Passed.",
        "Validating router OSPF neighborhood status -> Active / Full.",
        "Validating BGP peer status -> Established."
    ]
    
    rollback_executed = False
    rollback_logs = []
    
    if not verification_passed:
        verification_logs.append("CRITICAL: Verification loop failed! Duplicate IP/ping packet drop detected.")
        verification_logs.append("Verification FAILED. Triggering self-healing rollback...")
        
        rollback_executed = True
        rollback_logs = [
            "CRITICAL WARNING: Auto-Rollback triggered by verification failure.",
            f"Retrieving backup configuration point {backup_id}...",
            "Applying rollback script statements...",
            "Reloading original interfaces configuration state...",
            "SUCCESS: Original configuration state restored. Session safe."
        ]
    else:
        verification_logs.append("SUCCESS: All verification probes passed. Deployment healthy.")
        
        # Clear simulated outages dynamically upon successful configuration
        if device == "router-hq" and "isakmp" in commands.lower():
            active_scenarios_state["vpn_is_down"] = False
        elif device == "app-srv-02" and "kill" in commands.lower():
            active_scenarios_state["server_cpu_100"] = False
        elif "access-list" in commands.lower():
            active_scenarios_state["ssh_spray_attack"] = False
            AlarmService.resolve_alarm(db, "AL-8894")
        elif "var/log" in commands.lower() or "delete" in commands.lower():
            active_scenarios_state["log_partition_94"] = False
            AlarmService.resolve_alarm(db, "AL-8891")
            
    status_label = "Success" if verification_passed else "Failed (Rolled Back)"
    approvals = "Admin + Manager" if requires_dual else ("Manager" if role == "Senior Engineer" else "Admin")
    details = f"Deployed configuration patch to {device}. Result: {'Passed' if verification_passed else 'Failed, Auto-Rolled Back'}"
    
    # Audit log the deployment
    AuditService.log_audit_event(
        db=db,
        user_name=username,
        role=role,
        action="Deploy Config",
        ip="127.0.0.1",
        details=details,
        status=status_label,
        changes=commands,
        approvals=approvals,
        rollback=f"Executed: Restored {backup_id}" if rollback_executed else "N/A"
    )
    
    return {
        "success": verification_passed,
        "backupId": backup_id,
        "backupLogs": backup_logs,
        "deployLogs": "\n".join(deploy_logs),
        "verificationLogs": "\n".join(verification_logs),
        "rollbackExecuted": rollback_executed,
        "rollbackLogs": "\n".join(rollback_logs)
    }

# ----------------------------------------------------
# CONFIGURATION MANAGER (BACKUP, DIFF, DRIFT, ROLLBACK, APPROVALS)
# ----------------------------------------------------

class BackupRequest(BaseModel):
    device: str
    description: Optional[str] = ""

class DiffRequest(BaseModel):
    backupIdA: str
    backupIdB: str

class RollbackRequest(BaseModel):
    backupId: str

class ApprovalRequestSchema(BaseModel):
    device: str
    proposedConfig: str

class ApprovalActionSchema(BaseModel):
    requestId: str
    action: str  # "approve" or "reject"

class ScheduleRequest(BaseModel):
    device: str
    interval: str
    enabled: bool

@router.get("/config/backups")
async def api_get_backups(device: Optional[str] = None, user: dict = Depends(get_current_user)):
    return ConfigManagerService.get_backups(device)

@router.post("/config/backup")
async def api_create_backup(req: BackupRequest, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return ConfigManagerService.create_backup(req.device, req.description, db)

@router.post("/config/diff")
async def api_get_diff(req: DiffRequest, user: dict = Depends(get_current_user)):
    return ConfigManagerService.get_diff(req.backupIdA, req.backupIdB)

@router.get("/config/drift")
async def api_get_drift(device: str, user: dict = Depends(get_current_user)):
    return ConfigManagerService.get_drift_details(device)

@router.post("/config/rollback")
async def api_rollback(req: RollbackRequest, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return ConfigManagerService.rollback_to_backup(req.backupId, user["username"], user["role"], db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/config/approvals")
async def api_get_approvals(user: dict = Depends(get_current_user)):
    return ConfigManagerService.get_approval_requests()

@router.post("/config/approval/request")
async def api_create_approval_request(req: ApprovalRequestSchema, user: dict = Depends(get_current_user)):
    return ConfigManagerService.create_approval_request(req.device, req.proposedConfig, user["username"])

@router.post("/config/approval/action")
async def api_approval_action(req: ApprovalActionSchema, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        if req.action.lower() == "approve":
            return ConfigManagerService.approve_request(req.requestId, user["username"], user["role"], db)
        else:
            return ConfigManagerService.reject_request(req.requestId, user["username"], user["role"])
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.get("/config/schedules")
async def api_get_schedules(user: dict = Depends(get_current_user)):
    return ConfigManagerService.get_schedules()

@router.post("/config/schedule")
async def api_update_schedule(req: ScheduleRequest, user: dict = Depends(get_current_user)):
    return ConfigManagerService.update_schedule(req.device, req.interval, req.enabled)

