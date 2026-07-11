from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from typing import List

from api.deps import get_db, get_current_user
from schemas.discovery import DiscoveryRunRequest, DiscoveryScheduleRequest, DiscoveryLogResponse
from models.discovery import DiscoveryLog
from services.discovery import DiscoveryService
from services.audit import AuditService

router = APIRouter(prefix="/api/discovery", tags=["network-discovery"])

# Simple in-memory storage for active schedules
discovery_schedules = []

async def execute_background_discovery(subnet: str, db_session_factory):
    """
    Worker task running in background task loop
    """
    db = db_session_factory()
    try:
        await DiscoveryService.run_subnet_discovery(subnet, db)
    except Exception as e:
        print(f"[BACKGROUND DISCOVERY ERROR] {e}")
    finally:
        db.close()

@router.post("/run", status_code=202)
async def trigger_manual_discovery(
    req: DiscoveryRunRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Restricted to Admin, Operator, and Engineer roles
    if user["role"] not in ["Admin", "Operator", "Engineer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission Denied: Discovery sweeps restricted."
        )
        
    subnet = req.subnet.strip()
    if not subnet:
        raise HTTPException(status_code=400, detail="Missing subnet configuration.")
        
    # Launch scan in background task pool
    from database.session import SessionLocal
    background_tasks.add_task(execute_background_discovery, subnet, SessionLocal)
    
    AuditService.log_audit_event(
        db=db,
        user_name=user["username"],
        role=user["role"],
        action="Trigger Network Discovery",
        ip="127.0.0.1",
        details=f"Triggered manual network discovery sweep on subnet: {subnet}"
    )
    
    return {
        "status": "Running",
        "message": f"Subnet discovery sweep initiated for {subnet} in background."
    }

@router.post("/schedule")
async def configure_discovery_schedule(
    req: DiscoveryScheduleRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Restricted to Admin and Operator roles
    if user["role"] not in ["Admin", "Operator"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission Denied: Adjusting discovery schedules restricted."
        )
        
    subnet = req.subnet.strip()
    interval = req.intervalMinutes
    
    if not subnet or interval <= 0:
        raise HTTPException(status_code=400, detail="Invalid schedule configurations.")
        
    schedule = {
        "subnet": subnet,
        "intervalMinutes": interval,
        "active": True,
        "created_by": user["username"]
    }
    discovery_schedules.append(schedule)
    
    AuditService.log_audit_event(
        db=db,
        user_name=user["username"],
        role=user["role"],
        action="Schedule Network Discovery",
        ip="127.0.0.1",
        details=f"Scheduled discovery sweeps on {subnet} every {interval} minutes."
    )
    
    return {
        "status": "success",
        "message": f"Subnet discovery scheduled for {subnet} every {interval} minutes.",
        "schedule": schedule
    }

@router.get("/logs", response_model=List[DiscoveryLogResponse])
async def get_discovery_logs(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Visible to Admin, Operator, and Engineer roles
    if user["role"] not in ["Admin", "Operator", "Engineer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission Denied: Vault logs restricted."
        )
        
    logs = db.query(DiscoveryLog).order_by(DiscoveryLog.timestamp.desc()).all()
    return logs
