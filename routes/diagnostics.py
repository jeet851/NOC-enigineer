from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional

from api.deps import get_db, get_current_user
from schemas.diagnostics import SearchMemoryRequest, AnalyzePcapRequest, OCRDiagramRequest
from schemas.telemetry import TelemetryAlarmSchema  # or import custom
from services.alarm import AlarmService
from services.audit import AuditService
from workers.tasks import process_motadata_alert_task
from pydantic import BaseModel
import graph_ocr_packet

router = APIRouter(prefix="/api", tags=["diagnostics-and-webhooks"])

class MotadataAlertRequest(BaseModel):
    alertId: str
    hostIp: str
    monitorName: str
    severity: str
    message: str
    timestamp: Optional[str] = None

def get_documentation_markdown():
    return """# Enterprise Network Topology & Infrastructure Documentation
Prepared by: Zero-Trust AI Network Engineer
Compliance Standards: NIST SP 800-207, ISO 27001, OWASP

---

## 1. Zero-Trust Access Architecture
```mermaid
graph TD
    subgraph Users
        admin[Admin User]
        manager[Manager User]
        sen_eng[Senior Engineer]
        net_eng[Network Engineer]
        guest[Read-Only Guest]
    end

    subgraph Authentication
        mfa[Password + OTP + Challenge]
        vault[AES-256 Vault]
    end

    subgraph Production_Devices
        router[router-hq Edge Router]
        firewall[asa-edge-01 ASA Firewall]
        sw1[sw-core-01 Switch 1]
        sw2[sw-core-02 Switch 2]
    end

    Users --> mfa
    mfa --> vault
    vault --> Production_Devices
```

## 2. Managed Nodes Inventory
| Device Hostname | Vendor | Platform | IP Address | Current Status | Primary Function |
| --- | --- | --- | --- | --- | --- |
| `router-hq` | Cisco | IOS-XE | `198.51.100.2` | Healthy | HQ Edge Router / VPN Gateway |
| `asa-edge-01` | Cisco | ASA OS | `203.0.113.12` | Healthy | Perimeter Protection Firewall |
| `sw-core-01` | Cisco | Catalyst | `10.0.1.1` | Healthy | Core Layer-3 Routing Switch |
| `sw-core-02` | Cisco | Catalyst | `10.0.1.2` | Healthy | Core Layer-3 Routing Switch |
| `db-srv-01` | Linux | Ubuntu Server | `10.0.20.10` | Warning | Database Mount Core Partition |
| `app-srv-01` | Linux | Ubuntu Server | `10.0.10.5` | Healthy | DMZ Web Application Host |
| `app-srv-02` | Linux | Ubuntu Server | `10.0.10.6` | Healthy | DMZ Web Application Host |

## 3. VLAN Segregation Table
| VLAN ID | Name | Subnet Range | Gateway | Security Zone | Purpose / Description |
| --- | --- | --- | --- | --- | --- |
| `1` | Default | `10.0.1.0/24` | `10.0.1.254` | Administrative | Out-of-band management |
| `10` | Web_DMZ | `10.0.10.0/24` | `10.0.10.1` | DMZ (Zone 2) | Public web service worker ports |
| `20` | DB_Subnet | `10.0.20.0/24` | `10.0.20.1` | Internal Safe (Zone 3)| Database clustering segment |
| `99` | Native | `192.168.99.0/24` | N/A | Trunk native | Native Layer-2 trunk framing |
"""

@router.post("/ocr/analyze")
async def api_ocr_analyze(req: OCRDiagramRequest, user: dict = Depends(get_current_user)):
    return graph_ocr_packet.OCRDiagramParser.parse_diagram(req.imagepath)

@router.post("/packet/analyze")
async def api_packet_analyze(req: AnalyzePcapRequest, user: dict = Depends(get_current_user)):
    return graph_ocr_packet.PacketAnalyzer.analyze_pcap(req.filepath)

@router.post("/memory/search")
async def api_memory_search(req: SearchMemoryRequest, user: dict = Depends(get_current_user)):
    # Local vector search fallback
    vector_mem = graph_ocr_packet.VectorMemoryEngine()
    res = vector_mem.search_similar_incidents(req.query, top_k=2)
    return {"results": res}

@router.get("/documentation")
async def api_get_documentation(user: dict = Depends(get_current_user)):
    return {
        "markdown": get_documentation_markdown()
    }

@router.get("/documentation/download")
async def download_documentation(user: dict = Depends(get_current_user)):
    doc_content = get_documentation_markdown()
    return StreamingResponse(
        iter([doc_content]),
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=network_documentation.md"}
    )

@router.post("/v1/alerts/motadata")
async def api_motadata_alert(req: MotadataAlertRequest, db: Session = Depends(get_db)):
    # 1. Log alarm context in database
    AlarmService.add_alarm(
        db=db,
        alarm_id=req.alertId,
        source=req.hostIp,
        metric=req.monitorName,
        value=req.message,
        severity=req.severity,
        time_display="Just now"
    )
    
    # 2. Delegate closed-loop automated self-healing sweep to Celery background task (RabbitMQ message broker)
    process_motadata_alert_task.delay(req.dict())
    
    return {"status": "accepted", "alarmId": req.alertId}
