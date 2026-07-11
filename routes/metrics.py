from fastapi import APIRouter
import psutil
import time
import os

router = APIRouter(prefix="/api", tags=["metrics"])

# Basic request counters (in-memory tracking)
metrics_data = {
    "api_requests_total": 0,
    "process_start_time": time.time()
}

@router.get("/metrics")
async def get_metrics():
    """
    Exposes basic Prometheus-style telemetry metrics in JSON format.
    """
    uptime = time.time() - metrics_data["process_start_time"]
    pid = os.getpid()
    process = psutil.Process(pid)
    
    return {
        "process_uptime_seconds": uptime,
        "process_cpu_percent": process.cpu_percent(),
        "process_memory_bytes": process.memory_info().rss,
        "system_cpu_usage_percent": psutil.cpu_percent(),
        "system_memory_usage_percent": psutil.virtual_memory().percent,
        "active_threads_count": process.num_threads()
    }
