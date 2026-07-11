from fastapi import APIRouter
from monitoring.health import SystemHealthMonitor

router = APIRouter(prefix="/api", tags=["health"])

@router.get("/health")
async def health_check():
    db_status = await SystemHealthMonitor.get_database_status_async()
    redis_status = SystemHealthMonitor.get_redis_status()
    rabbitmq_status = SystemHealthMonitor.get_rabbitmq_status()
    system_load = SystemHealthMonitor.get_system_load()
    
    overall = "Healthy"
    if "Unhealthy" in db_status or "Unhealthy" in redis_status or "Unhealthy" in rabbitmq_status:
        overall = "Degraded"
        
    return {
        "status": overall,
        "services": {
            "database": db_status,
            "redis": redis_status,
            "rabbitmq": rabbitmq_status
        },
        "system": system_load
    }
