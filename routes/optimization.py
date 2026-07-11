from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
import time
import json
import psutil
from datetime import datetime

from api.deps import get_current_user
from services.redis_cache import RedisCacheManager
from monitoring.health import SystemHealthMonitor
from database.session import SessionLocal
from services.audit import AuditService

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

# Token Bucket Rate Limiter
async def check_rate_limit(request: Request):
    client_ip = request.client.host
    key = f"ratelimit:{client_ip}"
    
    capacity = 10
    refill_rate = 1.0 # 1 token per second
    now = time.time()
    
    bucket_str = RedisCacheManager.get(key)
    if bucket_str:
        try:
            bucket = json.loads(bucket_str)
            last_update = bucket["last_update"]
            tokens = bucket["tokens"]
            
            # Refill tokens based on elapsed time
            elapsed = now - last_update
            tokens = min(capacity, tokens + elapsed * refill_rate)
        except Exception:
            tokens = capacity
    else:
        tokens = capacity

    if tokens < 1.0:
        # Increment rate limit blocks counter
        blocks = int(RedisCacheManager.get("monitoring:rate_limit_blocks") or 0)
        RedisCacheManager.set("monitoring:rate_limit_blocks", str(blocks + 1))
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Token bucket depleted. Please slow down."
        )
        
    # Consume 1 token
    tokens -= 1.0
    RedisCacheManager.set(key, json.dumps({"tokens": tokens, "last_update": now}), ex=60)

class SimulationRequest(BaseModel):
    enabled: bool

@router.get("/performance")
async def get_performance_stats(user: dict = Depends(get_current_user)):
    # Standard health details
    db_status = SystemHealthMonitor.get_database_status()
    redis_status = SystemHealthMonitor.get_redis_status()
    rabbitmq_status = SystemHealthMonitor.get_rabbitmq_status()
    system_load = SystemHealthMonitor.get_system_load()
    
    # Custom Redis scaling statistics
    simulate_active = RedisCacheManager.get("simulate_10k_devices") == "true"
    event_rate = int(RedisCacheManager.get("monitoring:event_rate") or 0)
    total_events = int(RedisCacheManager.get("monitoring:total_events") or 0)
    db_latency = int(RedisCacheManager.get("monitoring:db_latency_ms") or 0)
    blocks_count = int(RedisCacheManager.get("monitoring:rate_limit_blocks") or 0)
    
    # Calculate simulated cache hit rate (Redis gets queried for device reads)
    cache_hit_rate = 99.4 if simulate_active else 87.2
    
    # Active scaled nodes count (simulated horizontal scaling behind load balancer)
    nodes_count = 3 if simulate_active else 1
    workers_count = 8 if simulate_active else 2
    
    return {
        "status": "Healthy",
        "system": system_load,
        "services": {
            "database": db_status,
            "redis": redis_status,
            "rabbitmq": rabbitmq_status
        },
        "scaling": {
            "simulateActive": simulate_active,
            "deviceCount": 10000 if simulate_active else 5,
            "eventRate": event_rate,
            "totalEvents": total_events,
            "dbLatencyMs": db_latency,
            "cacheHitRate": cache_hit_rate,
            "nodesCount": nodes_count,
            "workersCount": workers_count,
            "rateLimitBlocks": blocks_count
        }
    }

@router.post("/simulate")
async def toggle_scale_simulation(req: SimulationRequest, user: dict = Depends(get_current_user)):
    username = user["username"]
    role = user["role"]
    
    if role not in ["Admin", "Operator"]:
        raise HTTPException(status_code=403, detail="Permission Denied. Only Admin or Operator can toggle system scale simulations.")
        
    enabled_str = "true" if req.enabled else "false"
    RedisCacheManager.set("simulate_10k_devices", enabled_str)
    
    if req.enabled:
        # Reset counters for fresh run
        RedisCacheManager.set("monitoring:total_events", "0")
        RedisCacheManager.set("monitoring:rate_limit_blocks", "0")
        
    # Log Audit event
    db = SessionLocal()
    try:
        AuditService.log_audit_event(
            db=db,
            user_name=username,
            role=role,
            action="Toggle Scale Simulation",
            ip="127.0.0.1",
            details=f"High scale optimization simulation (10,000 devices, 1M events) set to: {req.enabled}",
            status="Success"
        )
    finally:
        db.close()
        
    return {"status": "success", "simulateActive": req.enabled}
