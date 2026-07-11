from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from api.deps import get_db, get_current_user
from schemas.incident import IncidentResponse
from models.incident import Incident
from services.incident import IncidentService
from services.audit import AuditService
from websocket.server import sio

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

@router.get("", response_model=List[IncidentResponse])
async def get_all_incidents(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Visible to Admin, Operator, and Engineer
    if user["role"] not in ["Admin", "Operator", "Engineer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission Denied: Incidents list access restricted."
        )
        
    return IncidentService.get_incidents(db)

@router.get("/active", response_model=List[IncidentResponse])
async def get_active_incidents(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Visible to Admin, Operator, and Engineer
    if user["role"] not in ["Admin", "Operator", "Engineer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission Denied: Incidents list access restricted."
        )
        
    return IncidentService.get_active_incidents(db)

@router.post("/{incident_id}/resolve")
async def resolve_incident_manually(
    incident_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Resolve requires Admin or Operator role
    if user["role"] not in ["Admin", "Operator"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission Denied: Manually resolving incidents is restricted to Admin/Operator roles."
        )
        
    resolved = IncidentService.resolve_incident(db, incident_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Incident not found.")
        
    AuditService.log_audit_event(
        db=db,
        user_name=user["username"],
        role=user["role"],
        action="Resolve Incident Manually",
        ip="127.0.0.1",
        details=f"Manually resolved incident: '{incident_id}'"
    )
    
    # Broadcast status change via Socket.IO
    await sio.emit("incident_update", {
        "id": incident_id,
        "status": "Resolved"
    })
    
    return {"status": "success", "message": f"Incident '{incident_id}' resolved successfully."}
