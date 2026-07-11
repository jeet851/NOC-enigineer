from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_user
from schemas.action import ActionRequest, ActionResponse
import ai_engine
import network_analyzers
import report_generator

router = APIRouter(prefix="/api", tags=["actions"])

@router.post("/action", response_model=ActionResponse)
async def trigger_action(req: ActionRequest, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    scenario_key = req.scenario.strip().lower().rstrip("?.- ")
    action = req.action
    
    scenario = ai_engine.SCENARIOS.get(scenario_key)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_key}' not found")
        
    if action == "diagnostics":
        device_map = {
            "vpn is down": "router-hq",
            "server cpu is 100%": "app-srv-02",
            "configure vlan 25": "sw-core-01",
            "configure vlan 20": "sw-core-01",
            "check daily server health": "db-srv-01",
            "analyze this firewall log": "asa-edge-01"
        }
        device = device_map.get(scenario_key, "router-hq")
        sweep_res = network_analyzers.TroubleshootingGraph.execute_sweep(device)
        output = (
            f"=== NOC COPILOT AUTOMATED DIAGNOSTIC SWEEP ===\n"
            f"Node Hostname: {device}\n"
            f"Standard Compliance: NIST SP 800-207 Zero-Trust\n"
            f"--------------------------------------------------\n"
            f"{sweep_res['logs']}\n"
            f"--------------------------------------------------\n"
            f"Verification Result: {sweep_res['status']}\n"
            f"Confidence Score: {sweep_res['confidence_score']}%\n"
            f"Proposed Solution: {sweep_res['remediation_plan'] or 'N/A'}\n"
        )
        return {"output": output}
        
    elif action == "rca":
        device_map = {
            "vpn is down": "router-hq",
            "server cpu is 100%": "app-srv-02",
            "configure vlan 25": "sw-core-01",
            "configure vlan 20": "sw-core-01",
            "check daily server health": "db-srv-01",
            "analyze this firewall log": "asa-edge-01"
        }
        device = device_map.get(scenario_key, "router-hq")
        sweep_res = network_analyzers.TroubleshootingGraph.execute_sweep(device)
        incident_details = {
            "device": device,
            "root_cause": sweep_res["logs"].split("\n")[-2] if len(sweep_res["logs"].split("\n")) > 1 else "Degraded protocol interface.",
            "cli_fix": sweep_res["remediation_plan"]
        }
        output = report_generator.ReportGenerator.generate_rca(scenario_key, incident_details)
        return {"output": output}
        
    # Return simulated playbook action output directly from AI engine mappings
    output = scenario.get(action, "Playbook command execution completed successfully.")
    return {"output": output}
