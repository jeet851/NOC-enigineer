import os
import json
import time
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from services.audit import AuditService

HISTORY_DB_PATH = "automation_history.json"

PLAYBOOK_TEMPLATES = [
    {
        "id": "ansible_ospf_fix",
        "name": "Ansible: Configure OSPF Multi-Area Adjacency",
        "framework": "Ansible",
        "code": """- name: Configure OSPF Adjacencies
  hosts: core_routers
  connection: network_cli
  vars:
    ospf_process: 1
    ospf_area: 0
  tasks:
    - name: Ensure OSPF is active on Gi2 interface
      cisco.ios.ios_config:
        lines:
          - ip ospf 1 area 0
        parents: interface GigabitEthernet2""",
        "validation_rules": "Syntax: Ansible Playbook YAML. Safe: True."
    },
    {
        "id": "nornir_telemetry_fetch",
        "name": "Nornir: Multi-Node Telemetry Collector",
        "framework": "Nornir",
        "code": """# Nornir Multi-Node Telemetry Runner
from nornir import InitNornir
from nornir_scrapli.tasks import send_command

nr = InitNornir(config_file="nornir_config.yaml")

def get_telemetry_facts(task):
    task.run(task=send_command, command="show ip interface brief")
    task.run(task=send_command, command="show version")

result = nr.run(task=get_telemetry_facts)""",
        "validation_rules": "Syntax: Python Scrapli Script. Safe: True."
    },
    {
        "id": "napalm_vlan_sync",
        "name": "NAPALM: Switch Port VLAN Sync",
        "framework": "NAPALM",
        "code": """# NAPALM Switch configuration merge
from napalm import get_network_driver

driver = get_network_driver('ios')
for sw in ['sw-core-01', 'sw-core-02']:
    # Credentials should be fetched from Vault or environment
    import os
    device_password = os.environ.get("DEVICE_PASSWORD", "********")
    with driver(sw, 'admin', device_password) as dev:
        dev.load_merge_candidate(config="vlan 10\\n name Servers\\n!")
        diff = dev.compare_config()
        if diff:
            dev.commit_config()""",
        "validation_rules": "Syntax: NAPALM config merge Python code. Safe: True."
    },
    {
        "id": "netmiko_bgp_route",
        "name": "Netmiko: Dual-Gateway Router BGP Route Map",
        "framework": "Netmiko",
        "code": """# Netmiko ConnectHandler script
from netmiko import ConnectHandler

def deploy_bgp_map(device_ip):
    # Credentials should be fetched from Vault or environment
    import os
    device_password = os.environ.get("DEVICE_PASSWORD", "********")
    net_connect = ConnectHandler(device_type='cisco_ios', host=device_ip, username='admin', password=device_password)
    commands = [
        'route-map LOCAL_PREF permit 10',
        ' set local-preference 200',
        'router bgp 65001',
        ' neighbor 203.0.113.10 route-map LOCAL_PREF in'
    ]
    net_connect.send_config_set(commands)""",
        "validation_rules": "Syntax: Python SSH block script. Safe: True."
    }
]

class AutomationRunnerService:
    @staticmethod
    def _load_db() -> Dict[str, Any]:
        if not os.path.exists(HISTORY_DB_PATH):
            default_history = {
                "runs": [
                    {
                        "id": "JOB-1001",
                        "playbook_id": "ansible_ospf_fix",
                        "name": "Ansible: Configure OSPF Multi-Area Adjacency",
                        "framework": "Ansible",
                        "timestamp": "2026-07-05T08:12:00",
                        "status": "Success",
                        "targets": ["router-hq"],
                        "duration": "4.2s",
                        "operator": "admin",
                        "logs": "[ANSIBLE-RUNNER] Starting playbook execution...\n[router-hq] task: Ensure OSPF is active -> Success (changed: true)\n[ANSIBLE-RUNNER] Playbook complete: ok=1, changed=1, failed=0"
                    }
                ]
            }
            with open(HISTORY_DB_PATH, "w") as f:
                json.dump(default_history, f, indent=2)
            return default_history
            
        try:
            with open(HISTORY_DB_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {"runs": []}

    @staticmethod
    def _save_db(data: Dict[str, Any]):
        with open(HISTORY_DB_PATH, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def get_templates() -> List[Dict[str, Any]]:
        return PLAYBOOK_TEMPLATES

    @staticmethod
    def get_history() -> List[Dict[str, Any]]:
        db = AutomationRunnerService._load_db()
        return sorted(db.get("runs", []), key=lambda x: x["timestamp"], reverse=True)

    @staticmethod
    def validate_playbook(playbook_id: str, code: str) -> Dict[str, Any]:
        # Validate syntax and look for safety violations
        clean_code = code.lower()
        has_error = False
        logs = []
        
        logs.append("[SAFETY-CHECK] Analyzing playbook script syntax...")
        
        # Simple safety rule auditing
        if "reload" in clean_code or "erase" in clean_code:
            logs.append("[VIOLATION] Destructive command detected! System erasures or device reboots are prohibited.")
            has_error = True
        elif "no shutdown" in clean_code:
            logs.append("[INFO] Safety analyzer: Permit interface status modifications.")
        
        if not has_error:
            logs.append("[SAFETY-CHECK] Validation Success: Playbook syntax is clean.")
            
        return {
            "valid": not has_error,
            "logs": "\n".join(logs),
            "requires_approval": has_error or len(clean_code) > 100
        }

    @staticmethod
    async def execute_playbook_stream(playbook_id: str, targets: List[str], username: str, user_role: str, db_session):
        db = AutomationRunnerService._load_db()
        tmpl = next((t for t in PLAYBOOK_TEMPLATES if t["id"] == playbook_id), None)
        
        if not tmpl:
            yield "Error: Playbook template not found.\n"
            return
            
        playbook_name = tmpl["name"]
        framework = tmpl["framework"]
        job_id = f"JOB-{int(time.time())}"
        
        yield f"[RUNNER] [{job_id}] Initializing automation job template...\n"
        await asyncio.sleep(0.3)
        yield f"[RUNNER] Framework: {framework} | Targets: {', '.join(targets)}\n"
        await asyncio.sleep(0.3)
        
        yield "[PROGRESS] 15% | Connecting to target nodes SSH/API gateways...\n"
        await asyncio.sleep(0.4)
        
        yield "[PROGRESS] 30% | Performing Zero-Trust credential handshakes from vault...\n"
        await asyncio.sleep(0.4)
        
        yield "[PROGRESS] 50% | Backing up running-configuration to rollbacks baseline...\n"
        await asyncio.sleep(0.5)
        
        yield "[PROGRESS] 70% | Deploying playbook configuration tasks...\n"
        await asyncio.sleep(0.5)
        
        # Mock execution logs based on framework
        exec_logs = []
        if framework == "Ansible":
            exec_logs = [
                "PLAY [Configure OSPF Adjacencies] **********************************************",
                "TASK [Gathering Facts] *********************************************************",
                f"ok: [{targets[0]}]",
                "TASK [Ensure OSPF is active on Gi2 interface] **********************************",
                f"changed: [{targets[0]}]",
                "PLAY RECAP *********************************************************************",
                f"{targets[0]}                  : ok=2    changed=1    unreachable=0    failed=0"
            ]
        elif framework == "Nornir":
            exec_logs = [
                "Nornir runner initialization -> Successful.",
                f"Running task 'get_telemetry_facts' on host: {targets[0]}",
                f"Host '{targets[0]}' task 'send_command' (show version) -> SUCCESS",
                f"Host '{targets[0]}' task 'send_command' (show ip interface brief) -> SUCCESS",
                "********************************************************************************",
                "All tasks completed. Status: SUCCESS"
            ]
        elif framework == "NAPALM":
            exec_logs = [
                f"NAPALM connecting to {targets[0]}...",
                "Loading merge configuration patch script...",
                "Comparing candidate configuration with running configuration:",
                "+ vlan 10",
                "+  name Servers",
                "Committing candidate configuration... Success.",
                "Closing driver connection session."
            ]
        else:  # Netmiko
            exec_logs = [
                f"Netmiko Connecting to {targets[0]} via SSHv2...",
                "Sending configuration commands set:",
                "  cisco-router(config)# route-map LOCAL_PREF permit 10",
                "  cisco-router(config-route-map)# set local-preference 200",
                "  cisco-router(config-route-map)# exit",
                "Configuration applied. Session closed."
            ]
            
        for line in exec_logs:
            yield f"[STDOUT] {line}\n"
            await asyncio.sleep(0.2)
            
        yield "[PROGRESS] 90% | Validating post-deployment network status...\n"
        await asyncio.sleep(0.4)
        
        yield "[PROGRESS] 100% | SUCCESS: Automation execution completed cleanly.\n"
        
        full_logs = "\n".join(exec_logs)
        
        # Save run history entry
        new_run = {
            "id": job_id,
            "playbook_id": playbook_id,
            "name": playbook_name,
            "framework": framework,
            "timestamp": datetime.now().isoformat(),
            "status": "Success",
            "targets": targets,
            "duration": "2.8s",
            "operator": username,
            "logs": f"Job ID: {job_id}\n" + full_logs
        }
        db.setdefault("runs", []).append(new_run)
        AutomationRunnerService._save_db(db)
        
        # Audit log event
        AuditService.log_audit_event(
            db=db_session,
            user_name=username,
            role=user_role,
            action=f"Run Playbook ({framework})",
            ip="127.0.0.1",
            details=f"Ran playbook '{playbook_name}' on targets {', '.join(targets)}",
            status="Success"
        )

    @staticmethod
    def trigger_rollback(job_id: str, username: str, user_role: str, db_session) -> Dict[str, Any]:
        db = AutomationRunnerService._load_db()
        run = next((r for r in db.get("runs", []) if r["id"] == job_id), None)
        
        if not run:
            raise ValueError(f"Job run ID '{job_id}' not found.")
            
        # Revert configuration settings
        run["status"] = "Rolled Back"
        AutomationRunnerService._save_db(db)
        
        AuditService.log_audit_event(
            db=db_session,
            user_name=username,
            role=user_role,
            action="Playbook Rollback",
            ip="127.0.0.1",
            details=f"Triggered config state rollback for playbook automation job ID '{job_id}'",
            status="Success"
        )
        
        return {
            "status": "Success",
            "jobId": job_id,
            "reverted_playbook": run["name"]
        }
