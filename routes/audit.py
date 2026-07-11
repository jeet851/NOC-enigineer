from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from api.deps import get_db, get_current_user
from schemas.audit import AuditLogSchema
from services.audit import AuditService

router = APIRouter(prefix="/api", tags=["audit-logs"])

@router.get("/audit-logs", response_model=List[AuditLogSchema])
async def api_get_audit_logs(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    logs = AuditService.get_audit_logs(db)
    
    # Map 'user_name' database field to 'user' for frontend rendering compatibility
    results = []
    for l in logs:
        # Convert SQLAlchemy object to dictionary or construct response model
        data = {
            "id": l.id,
            "timestamp": l.timestamp,
            "user_name": l.user_name,
            "user": l.user_name,  # frontend matches '.user'
            "role": l.role,
            "ip": l.ip,
            "action": l.action,
            "details": l.details,
            "status": l.status,
            "changes": l.changes,
            "approvals": l.approvals,
            "rollback": l.rollback
        }
        results.append(data)
        
    return results
