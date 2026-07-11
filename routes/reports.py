from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from services.report_exporter import ReportExporterService

from api.deps import get_db, get_current_user
from schemas.report import GenerateReportRequest, GenerateReportResponse
from reports.generator import SecurityReportGenerator
from routes.telemetry import calculate_network_scores
import network_analyzers

router = APIRouter(prefix="/api/reports", tags=["reports"])

@router.post("/generate", response_model=GenerateReportResponse)
async def api_generate_report(req: GenerateReportRequest, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    scenario_key = req.scenario.strip().lower().rstrip("?.- ")
    report_type = req.reportType.strip().lower()
    
    device_map = {
        "vpn is down": "router-hq",
        "server cpu is 100%": "app-srv-02",
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
    
    doc_content = ""
    if report_type == "rca":
        doc_content = SecurityReportGenerator.generate_rca(scenario_key, incident_details)
    elif report_type == "mop":
        doc_content = SecurityReportGenerator.generate_mop(scenario_key, sweep_res["remediation_plan"] or "No changes", device)
    elif report_type == "sop":
        doc_content = SecurityReportGenerator.generate_sop(scenario_key)
    elif report_type == "executive":
        scores = calculate_network_scores()
        doc_content = SecurityReportGenerator.generate_executive_summary(scores, 2)
    else:
        raise HTTPException(status_code=400, detail="Invalid report type.")
        
    return {"markdown": doc_content}

@router.get("/export")
async def api_export_report(
    format: str,
    user: dict = Depends(get_current_user)
):
    fmt = format.lower().strip()
    if fmt == "json":
        return Response(
            content=ReportExporterService.export_json(),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=operations_report.json"}
        )
    elif fmt == "csv":
        return Response(
            content=ReportExporterService.export_csv(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=operations_report.csv"}
        )
    elif fmt == "pdf":
        return Response(
            content=ReportExporterService.export_pdf(),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=operations_report.pdf"}
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid export format. Must be JSON, CSV, or PDF.")
