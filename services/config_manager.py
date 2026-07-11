import os
import json
import difflib
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.config_backup import ConfigBackupRepository
from models.config_backup import ConfigurationBackup
from services.audit import AuditService

JSON_DB_PATH = "config_backups.json"

# In-memory baseline configurations dictionary
BASELINE_CONFIGS = {
    "router-hq": """hostname router-hq
!
interface GigabitEthernet1
 description WAN-Link-Interface
 ip address 198.51.100.2 255.255.255.0
!
interface GigabitEthernet2
 description LAN-Gateway-Segment
 ip address 10.0.1.254 255.255.255.0
!
router ospf 1
 network 10.0.0.0 0.255.255.255 area 0
!
ip route 0.0.0.0 0.0.0.0 198.51.100.1
!
end""",
    "asa-edge-01": """hostname asa-edge-01
!
interface GigabitEthernet0/0
 nameif outside
 security-level 0
 ip address 203.0.113.12 255.255.255.0
!
interface GigabitEthernet0/1
 nameif inside
 security-level 100
 ip address 10.0.1.1 255.255.255.0
!
access-list OUTSIDE_IN extended permit tcp any host 10.0.10.5 eq 80
!
end""",
    "sw-core-01": """hostname sw-core-01
!
vlan 10
 name Servers
vlan 20
 name Users
!
interface GigabitEthernet1/1
 switchport mode trunk
!
end"""
}

# Current live config configurations (potentially drifted)
LIVE_CONFIGS = {
    "router-hq": """hostname router-hq
!
interface GigabitEthernet1
 description WAN-Link-Interface
 ip address 198.51.100.2 255.255.255.0
 ip ospf cost 55
!
interface GigabitEthernet2
 description LAN-Gateway-Segment
 ip address 10.0.1.254 255.255.255.0
!
router ospf 1
 network 10.0.0.0 0.255.255.255 area 0
 network 192.168.1.0 0.0.0.255 area 10
!
ip route 0.0.0.0 0.0.0.0 198.51.100.1
!
end""",
    "asa-edge-01": """hostname asa-edge-01
!
interface GigabitEthernet0/0
 nameif outside
 security-level 0
 ip address 203.0.113.12 255.255.255.0
!
interface GigabitEthernet0/1
 nameif inside
 security-level 100
 ip address 10.0.1.1 255.255.255.0
!
access-list OUTSIDE_IN extended permit tcp any host 10.0.10.5 eq 80
access-list OUTSIDE_IN extended permit tcp any host 10.0.20.10 eq 22
!
end""",
    "sw-core-01": """hostname sw-core-01
!
vlan 10
 name Servers
vlan 20
 name Users
!
interface GigabitEthernet1/1
 switchport mode trunk
!
end"""
}

class ConfigManagerService:
    backup_repo = ConfigBackupRepository()

    @staticmethod
    def _load_db() -> Dict[str, Any]:
        """
        Keeps local schedules and approvals structure in JSON for simplicity.
        """
        if not os.path.exists(JSON_DB_PATH):
            default_db = {
                "schedules": [
                    {"device": "router-hq", "interval": "Daily at 02:00", "enabled": True},
                    {"device": "asa-edge-01", "interval": "Weekly on Sundays", "enabled": True},
                    {"device": "sw-core-01", "interval": "Daily at 03:00", "enabled": False}
                ],
                "approvals": [
                    {
                        "id": "APP-2001",
                        "device": "router-hq",
                        "proposed_config": "interface GigabitEthernet2\n shutdown",
                        "requested_by": "engineer",
                        "status": "Pending Approval",
                        "timestamp": "2026-07-05T10:15:00"
                    }
                ]
            }
            with open(JSON_DB_PATH, "w") as f:
                json.dump(default_db, f, indent=2)
            return default_db
            
        try:
            with open(JSON_DB_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {"schedules": [], "approvals": []}

    @staticmethod
    def _save_db(data: Dict[str, Any]):
        with open(JSON_DB_PATH, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    async def get_backups(db: AsyncSession, device: Optional[str] = None) -> List[ConfigurationBackup]:
        if device:
            return await ConfigManagerService.backup_repo.get_by_device(db, device)
        return await ConfigManagerService.backup_repo.get_all(db)

    @staticmethod
    async def create_backup(device: str, description: str, db: AsyncSession) -> ConfigurationBackup:
        # Pull live configuration representing active state
        running_cfg = LIVE_CONFIGS.get(device, BASELINE_CONFIGS.get(device, "! Configuration unavailable."))
        startup_cfg = BASELINE_CONFIGS.get(device, "! Startup configuration unavailable.")
        
        # Calculate next version
        latest_ver = await ConfigManagerService.backup_repo.get_latest_version(db, device)
        next_ver = latest_ver + 1
        
        bck_id = f"CFG_BCK_{device.upper()}_{int(datetime.now().timestamp())}"
        new_backup = ConfigurationBackup(
            id=bck_id,
            device_name=device,
            timestamp=datetime.utcnow(),
            running_config=running_cfg,
            startup_config=startup_cfg,
            version=next_ver,
            description=description or f"Manual configuration backup V{next_ver}",
            created_by="system"
        )
        
        await ConfigManagerService.backup_repo.create(db, new_backup)
        
        # Update baseline target in memory for drift checks
        BASELINE_CONFIGS[device] = running_cfg
        
        return new_backup

    @staticmethod
    async def get_diff(db: AsyncSession, backup_id_a: str, backup_id_b: str) -> List[Dict[str, Any]]:
        bck_a = await ConfigManagerService.backup_repo.get(db, backup_id_a)
        bck_b = await ConfigManagerService.backup_repo.get(db, backup_id_b)
        
        if not bck_a or not bck_b:
            return []
            
        lines_a = bck_a.running_config.splitlines()
        lines_b = bck_b.running_config.splitlines()
        
        diff = difflib.ndiff(lines_a, lines_b)
        
        parsed_diff = []
        for line in diff:
            op = line[0]
            val = line[2:]
            if op == '+':
                parsed_diff.append({"type": "addition", "text": val})
            elif op == '-':
                parsed_diff.append({"type": "deletion", "text": val})
            else:
                parsed_diff.append({"type": "neutral", "text": val})
        return parsed_diff

    @staticmethod
    def get_drift_details(device: str) -> Dict[str, Any]:
        baseline = BASELINE_CONFIGS.get(device, "").strip()
        live = LIVE_CONFIGS.get(device, "").strip()
        
        if not baseline or not live:
            return {"has_drift": False, "diff": []}
            
        lines_base = baseline.splitlines()
        lines_live = live.splitlines()
        
        diff = list(difflib.ndiff(lines_base, lines_live))
        has_drift = any(line.startswith('+') or line.startswith('-') for line in diff)
        
        parsed_diff = []
        for line in diff:
            op = line[0]
            val = line[2:]
            if op == '+':
                parsed_diff.append({"type": "addition", "text": val})
            elif op == '-':
                parsed_diff.append({"type": "deletion", "text": val})
            else:
                parsed_diff.append({"type": "neutral", "text": val})
                
        return {
            "has_drift": has_drift,
            "device": device,
            "last_checked": datetime.now().isoformat(),
            "diff": parsed_diff
        }

    @staticmethod
    async def rollback_to_backup(backup_id: str, user_name: str, user_role: str, db: AsyncSession) -> Dict[str, Any]:
        bck = await ConfigManagerService.backup_repo.get(db, backup_id)
        if not bck:
            raise ValueError(f"Backup reference '{backup_id}' not found.")
            
        device = bck.device_name
        restored_cfg = bck.running_config
        
        # Apply backup content directly to live device config
        LIVE_CONFIGS[device] = restored_cfg
        BASELINE_CONFIGS[device] = restored_cfg
        
        # Log event in Security Audit Logs
        await AuditService.log_audit_event(
            db=db,
            user_name=user_name,
            role=user_role,
            action="Config Rollback",
            ip="127.0.0.1",
            details=f"Rolled back device '{device}' configuration to version V{bck.version} ({backup_id})",
            status="Success",
            changes=f"Restored configuration backup version {bck.version}"
        )
        
        return {
            "status": "Success",
            "device": device,
            "backupId": backup_id,
            "version": bck.version
        }

    @staticmethod
    def get_approval_requests() -> List[Dict[str, Any]]:
        db_json = ConfigManagerService._load_db()
        return db_json.get("approvals", [])

    @staticmethod
    def create_approval_request(device: str, proposed_config: str, requester: str) -> Dict[str, Any]:
        db_json = ConfigManagerService._load_db()
        req_id = f"APP-{int(datetime.now().timestamp())}"
        new_request = {
            "id": req_id,
            "device": device,
            "proposed_config": proposed_config,
            "requested_by": requester,
            "status": "Pending Approval",
            "timestamp": datetime.now().isoformat()
        }
        db_json.setdefault("approvals", []).append(new_request)
        ConfigManagerService._save_db(db_json)
        return new_request

    @staticmethod
    async def approve_request(request_id: str, approver_name: str, approver_role: str, db: AsyncSession) -> Dict[str, Any]:
        db_json = ConfigManagerService._load_db()
        req = next((r for r in db_json.get("approvals", []) if r["id"] == request_id), None)
        
        if not req:
            raise ValueError(f"Approval request '{request_id}' not found.")
            
        if approver_role not in ["Admin", "Operator"]:
            raise PermissionError("Only Administrators and Operators can approve configuration deployments.")
            
        device = req["device"]
        proposed = req["proposed_config"]
        
        # Execute / Apply config to live
        original = LIVE_CONFIGS.get(device, "")
        LIVE_CONFIGS[device] = original + "\n" + proposed
        
        req["status"] = "Approved"
        req["approved_by"] = approver_name
        req["approved_at"] = datetime.now().isoformat()
        
        ConfigManagerService._save_db(db_json)
        
        # Log audit trail
        await AuditService.log_audit_event(
            db=db,
            user_name=approver_name,
            role=approver_role,
            action="Approve Configuration",
            ip="127.0.0.1",
            details=f"Approved and deployed proposed configuration changes on '{device}' requested by '{req['requested_by']}'",
            status="Success",
            changes=proposed
        )
        
        return req

    @staticmethod
    def reject_request(request_id: str, rejecter_name: str, rejecter_role: str) -> Dict[str, Any]:
        db_json = ConfigManagerService._load_db()
        req = next((r for r in db_json.get("approvals", []) if r["id"] == request_id), None)
        
        if not req:
            raise ValueError(f"Approval request '{request_id}' not found.")
            
        req["status"] = "Rejected"
        req["rejected_by"] = rejecter_name
        req["rejected_at"] = datetime.now().isoformat()
        
        ConfigManagerService._save_db(db_json)
        return req

    @staticmethod
    def get_schedules() -> List[Dict[str, Any]]:
        db_json = ConfigManagerService._load_db()
        return db_json.get("schedules", [])

    @staticmethod
    def update_schedule(device: str, interval: str, enabled: bool) -> Dict[str, Any]:
        db_json = ConfigManagerService._load_db()
        sched = next((s for s in db_json.get("schedules", []) if s["device"] == device), None)
        if sched:
            sched["interval"] = interval
            sched["enabled"] = enabled
        else:
            sched = {"device": device, "interval": interval, "enabled": enabled}
            db_json.setdefault("schedules", []).append(sched)
            
        ConfigManagerService._save_db(db_json)
        return sched
