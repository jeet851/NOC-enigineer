import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from services.automation_runner import AutomationRunnerService

router = APIRouter(prefix="/api/automation", tags=["automation"])

class PlaybookValidationRequest(BaseModel):
    playbookId: str
    code: str

class PlaybookExecutionRequest(BaseModel):
    playbookId: str
    targets: List[str]

class RollbackJobRequest(BaseModel):
    jobId: str

@router.get("/templates")
async def api_get_templates(user: dict = Depends(get_current_user)):
    return AutomationRunnerService.get_templates()

@router.get("/history")
async def api_get_history(user: dict = Depends(get_current_user)):
    return AutomationRunnerService.get_history()

@router.post("/validate")
async def api_validate(req: PlaybookValidationRequest, user: dict = Depends(get_current_user)):
    return AutomationRunnerService.validate_playbook(req.playbookId, req.code)

@router.post("/execute")
async def api_execute(
    req: PlaybookExecutionRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user["role"] not in ["Admin", "Operator", "Engineer"]:
        raise HTTPException(status_code=403, detail="Permission Denied: Automation execution blocked.")
        
    return StreamingResponse(
        AutomationRunnerService.execute_playbook_stream(
            playbook_id=req.playbookId,
            targets=req.targets,
            username=user["username"],
            user_role=user["role"],
            db_session=db
        ),
        media_type="text/plain"
    )

@router.post("/rollback")
async def api_rollback(
    req: RollbackJobRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        return AutomationRunnerService.trigger_rollback(req.jobId, user["username"], user["role"], db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
