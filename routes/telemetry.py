import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import json
import random
import os
from typing import Dict, Any

from api.deps import get_db
from api.config import settings
from services.device import DeviceService
from services.telemetry import TelemetryService
from services.alarm import AlarmService
from services.redis_cache import RedisCacheManager
from routes.config import active_scenarios_state
import ai_engine

logger = logging.getLogger("noc.telemetry")

router = APIRouter(prefix="/api", tags=["telemetry"])

def calculate_network_scores() -> Dict[str, int]:
    scores = {
        "physical": 98,
        "layer2": 95,
        "layer3": 96,
        "routing": 94,
        "firewall": 90,
        "vpn": 95,
        "cloud": 98,
        "overall": 95
    }
    
    if active_scenarios_state.get("vpn_is_down", False):
        scores["vpn"] -= 50
        scores["routing"] -= 20
        scores["layer3"] -= 15
        
    if active_scenarios_state.get("server_cpu_100", False):
        scores["physical"] -= 10
        
    if active_scenarios_state.get("log_partition_94", False):
        scores["physical"] -= 5
        
    if active_scenarios_state.get("ssh_spray_attack", False):
        scores["firewall"] -= 40
        
    scores["overall"] = int(sum(scores.values()) / (len(scores) - 1))
    return scores

@router.get("/telemetry")
async def get_telemetry(db: Session = Depends(get_db)):
    if RedisCacheManager.ping():
        try:
            cached_data = RedisCacheManager.get("noc_telemetry_cache")
            if cached_data:
                return json.loads(cached_data)
        except Exception:
            pass

    # Overall score calculation
    scores = calculate_network_scores()
    
    nodes = []
    db_devices = DeviceService.get_all_devices(db)
    
    for dev in db_devices:
        logs = TelemetryService.get_latest_telemetry(db, dev.name, limit=1)
        cpu = random.randint(5, 20)
        ram = random.randint(45, 55)
        status = dev.status
        
        # Apply simulated status overrides
        if dev.name == "router-hq":
            status = "Warning" if active_scenarios_state.get("vpn_is_down", False) else "Healthy"
        elif dev.name == "app-srv-02":
            status = "Warning" if active_scenarios_state.get("server_cpu_100", False) else "Healthy"
        elif dev.name == "db-srv-01":
            status = "Warning" if active_scenarios_state.get("log_partition_94", False) else "Healthy"
        elif dev.name == "asa-edge-01":
            status = "Warning" if active_scenarios_state.get("ssh_spray_attack", False) else "Healthy"
            
        message = None
        
        if logs:
            cpu = logs[0].cpu
            ram = logs[0].ram
            
        if dev.name == "db-srv-01" and active_scenarios_state.get("log_partition_94", False):
            message = "Log Partition at 94%"
            
        nodes.append({
            "name": f"{dev.name} ({dev.role})",
            "status": status,
            "message": message,
            "cpu": cpu,
            "ram": ram
        })
        
    alarms = []
    db_alarms = AlarmService.get_active_alarms(db)
    for al in db_alarms:
        alarms.append({
            "id": al.id,
            "source": al.source,
            "metric": al.metric,
            "value": al.value,
            "severity": al.severity,
            "time": al.time_display
        })
        
    gemini_active = ai_engine.gemini_available
    
    bot_token = settings.SLACK_BOT_TOKEN
    app_token = settings.SLACK_APP_TOKEN
    slack_active = False
    if bot_token and app_token and "your-bot-token" not in bot_token and "your-app-token" not in app_token:
        slack_active = True
        
    telemetry_data = {
        "metrics": {
            "cpu": random.randint(22, 54),
            "ram": random.randint(48, 67),
            "disk": 68,
            "network": random.randint(320, 840),
            "sla": 99.98
        },
        "nodes": nodes,
        "alarms": alarms,
        "geminiActive": gemini_active,
        "slackActive": slack_active
    }

    try:
        RedisCacheManager.set(
            "noc_telemetry_cache",
            json.dumps(telemetry_data),
            ex=settings.REDIS_CACHE_TTL_SECONDS
        )
    except Exception:
        pass
            
    return telemetry_data
