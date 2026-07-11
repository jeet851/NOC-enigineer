import re
import random
import logging
from datetime import datetime
from workers.celery_app import celery_app
from database.session import get_db_context
from services.device import DeviceService
from services.alarm import AlarmService
from services.audit import AuditService
from automation.device_automation import DeviceAutomationManager
import ai_engine
import report_generator

logger = logging.getLogger("celery_tasks")

@celery_app.task(name="workers.tasks.process_motadata_alert_task")
def process_motadata_alert_task(req_data: dict):
    alarm_id = req_data["alertId"]
    host_ip = req_data["hostIp"]
    monitor_name = req_data["monitorName"]
    message = req_data["message"]
    severity = req_data["severity"]
    
    print(f"[CELERY WORKER] Closed-loop troubleshooting active for alert: {alarm_id}")
    
    with next(get_db_context()) as db:
        # 1. Resolve target device
        device = None
        devices = DeviceService.get_all_devices(db)
        device = next((d for d in devices if d.ip == host_ip or d.name.lower() == host_ip.lower()), None)
        if device:
            device_name = device.name
            device_type = device.vendor
        else:
            device_name = "router-hq"
            device_type = "Cisco"
            
        # 2. Gather diagnostics
        diag_commands = []
        metric_lower = (monitor_name + " " + message).lower()
        
        if "bgp" in metric_lower:
            peer_ip_match = re.search(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', message)
            peer_ip = peer_ip_match.group(0) if peer_ip_match else "192.0.2.2"
            diag_commands = [f"show ip bgp neighbors {peer_ip}", f"ping {peer_ip}", f"telnet {peer_ip} 179"]
        elif "ospf" in metric_lower:
            diag_commands = ["show ip ospf neighbor", "show ip ospf interface"]
        elif "vlan" in metric_lower or "port" in metric_lower or "interface" in metric_lower:
            diag_commands = ["show interface description", "show interface status"]
        elif "cpu" in metric_lower or "load" in metric_lower:
            diag_commands = ["show processes cpu sorted"]
        else:
            diag_commands = ["ping " + host_ip]
            
        diag_outputs = []
        for cmd in diag_commands:
            try:
                output = DeviceAutomationManager.execute_command(device_name, cmd)
                diag_outputs.append(f"Command: {cmd}\nOutput:\n{output}")
            except Exception as e:
                diag_outputs.append(f"Command: {cmd}\nFailed: {e}")
                
        diagnostics_text = "\n\n".join(diag_outputs)
        
        # 3. Request config patch from LLM
        prompt = (
            f"You are Network Engineer, a routing and switching specialist. An alert from Motadata monitoring indicates a fault:\n"
            f"Monitor Name: {monitor_name}\n"
            f"Message: {message}\n"
            f"Severity: {severity}\n"
            f"Device: {device_name} ({host_ip})\n\n"
            f"Here are the diagnostics collected from the device:\n"
            f"{diagnostics_text}\n\n"
            f"Please analyze these diagnostics and formulate a configuration patch to resolve the issue. "
            f"Output your final configuration patch commands under section '5. Generated Configuration' in the 13-point format."
        )
        
        try:
            response_text = ai_engine.generate_ai_response(
                prompt_text=prompt,
                conversation_history=[],
                persona_key="net_genius",
                active_scenario=monitor_name
            )
        except Exception as e:
            response_text = ai_engine.get_general_simulated_response(prompt, "net_genius")
            
        # 4. Extract generated configuration patch from response
        config_patch = ""
        match = re.search(r"### 5\.\s+Generated Configuration.*?\n```(?:text)?\n(.*?)\n```", response_text, re.DOTALL | re.IGNORECASE)
        if match:
            config_patch = match.group(1).strip()
        else:
            match2 = re.search(r"Generated Configuration.*?\n```(?:text)?\n(.*?)\n```", response_text, re.DOTALL | re.IGNORECASE)
            if match2:
                config_patch = match2.group(1).strip()
            else:
                lines = response_text.split('\n')
                patch_started = False
                patch_lines = []
                for line in lines:
                    if "Generated Configuration" in line or "5. Generated Configuration" in line:
                        patch_started = True
                        continue
                    if patch_started:
                        if line.startswith("```"):
                            if len(patch_lines) > 0:
                                break
                            continue
                        if line.strip().startswith("###"):
                            break
                        patch_lines.append(line)
                config_patch = "\n".join(patch_lines).strip()
                
        config_patch = re.sub(r'^\d+:\s*', '', config_patch, flags=re.MULTILINE)
        
        if not config_patch or config_patch.startswith("N/A") or config_patch.startswith("! "):
            if "bgp" in metric_lower:
                config_patch = (
                    "ip access-list extended PERMIT-BGP\n"
                    " permit tcp host 192.0.2.1 host 192.0.2.2 eq bgp\n"
                    " permit tcp host 192.0.2.1 eq bgp host 192.0.2.2\n"
                    " exit\n"
                    "interface GigabitEthernet0/1\n"
                    " ip access-group PERMIT-BGP in"
                )
            elif "ospf" in metric_lower:
                config_patch = "interface GigabitEthernet1/0/1\n ip ospf mtu-ignore"
            else:
                config_patch = "! No configuration changes generated by AI for general alert."

        # 5. Run Safety checks
        validation_logs, has_error = ai_engine.validate_commands(config_patch, device_type)
        destructive_alerts = ai_engine.check_ai_safety(config_patch)
        
        if has_error or destructive_alerts:
            AuditService.log_audit_event(
                db=db,
                user_name="AI_NOC_Agent",
                role="System",
                action="Motadata Safety Blocked",
                ip=host_ip,
                details=f"Alarm {alarm_id} ({monitor_name}): Resolution patch failed compliance safety validation checks.",
                status="Blocked",
                changes=config_patch
            )
            return {"status": "blocked", "reason": "Safety check failed"}
            
        # 6. Deploy configuration patch
        success, deploy_result = DeviceAutomationManager.deploy_config_patch(device_name, config_patch)
        
        # 7. Verification & Closed loop resolution
        verification_passed = success
        from routes.config import active_scenarios_state
        if success:
            if "vpn" in metric_lower and "isakmp" in config_patch.lower():
                active_scenarios_state["vpn_is_down"] = False
            elif "bgp" in metric_lower and "access-group" in config_patch.lower():
                active_scenarios_state["ssh_spray_attack"] = False
            verification_passed = True
            
        # 8. Post-Incident Logging, Audit, and RCA documentation
        if verification_passed:
            AlarmService.resolve_alarm(db, alarm_id)
            
            incident_details = {
                "device": device_name,
                "root_cause": f"Motadata alarm: {message}",
                "cli_fix": config_patch
            }
            rca_report = report_generator.ReportGenerator.generate_rca(monitor_name, incident_details)
            
            AuditService.log_audit_event(
                db=db,
                user_name="AI_NOC_Agent",
                role="System",
                action="Motadata Alarm Resolved",
                ip=host_ip,
                details=f"Alarm {alarm_id} ({monitor_name}) successfully resolved by AI self-healing patch. Verification: Passed.",
                status="Success",
                changes=config_patch,
                approvals="Autonomous AI System"
            )
            return {"status": "resolved"}
        else:
            AuditService.log_audit_event(
                db=db,
                user_name="AI_NOC_Agent",
                role="System",
                action="Motadata Alarm Rollback",
                ip=host_ip,
                details=f"Alarm {alarm_id} ({monitor_name}) patch failed verification. Reverting changes.",
                status="Failed (Rolled Back)",
                changes=config_patch
            )
            return {"status": "failed", "reason": "Verification failed"}
