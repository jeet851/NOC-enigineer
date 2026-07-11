from fastapi import APIRouter, Depends
from api.deps import get_current_user
from schemas.settings import SettingsRequest, SettingsResponse

router = APIRouter(prefix="/api", tags=["settings"])

# System-wide dynamic configurations (module singleton state)
monitor_interval_seconds = 10
auto_healing_policy = "approval"  # "approval" or "autonomous"
alert_severity_threshold = 3      # 1=Info, 2=Warning, 3=Critical, 4=Disaster

@router.get("/settings", response_model=SettingsResponse)
async def get_settings(user: dict = Depends(get_current_user)):
    return {
        "interval": monitor_interval_seconds,
        "healingPolicy": auto_healing_policy,
        "severityThreshold": alert_severity_threshold
    }

@router.post("/settings")
async def save_settings(req: SettingsRequest, user: dict = Depends(get_current_user)):
    global monitor_interval_seconds, auto_healing_policy, alert_severity_threshold
    if req.interval is not None:
        monitor_interval_seconds = req.interval
        # Update collector directly
        import telemetry.collector
        telemetry.collector.monitor_interval_seconds = req.interval
    if req.healingPolicy is not None:
        auto_healing_policy = req.healingPolicy
    if req.severityThreshold is not None:
        alert_severity_threshold = req.severityThreshold
    return {"status": "success", "message": "Settings updated"}
