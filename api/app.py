import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from api.config import settings
from api.exceptions import register_exception_handlers
from core.logger import setup_logging

# Initialize structured JSON logging for the application
setup_logging()

from routes import (
    auth, chat, action, settings as settings_routes, config,
    vault, audit, telemetry, health, reports, topology,
    diagnostics, discovery, incident, cli, packets,
    automation, knowledge_base, zero_trust, optimization,
    metrics
)

app = FastAPI(title="Zero-Trust AI NOC Server", version="2.0.0")

# 1. CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Zero-Trust Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    csp_policy = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        "img-src 'self' data:; "
        "connect-src 'self';"
    )
    response.headers["Content-Security-Policy"] = csp_policy
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# 3. Exception Handlers Registration
register_exception_handlers(app)

# 4. Include legacy /api routes (for backward compatibility)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(action.router)
app.include_router(settings_routes.router)
app.include_router(config.router)
app.include_router(vault.router)
app.include_router(audit.router)
app.include_router(telemetry.router)
app.include_router(health.router)
app.include_router(reports.router)
app.include_router(topology.router)
app.include_router(diagnostics.router)
app.include_router(discovery.router)
app.include_router(incident.router)
app.include_router(cli.router)
app.include_router(packets.router)
app.include_router(automation.router)
app.include_router(knowledge_base.router)
app.include_router(zero_trust.router)
app.include_router(optimization.router)
app.include_router(metrics.router)

# 5. Include versioned /api/v1 router
# (Importing and mounting V1 router after legacy routes are registered to dynamically clean prefixes)
from api.v1.router import v1_router
app.include_router(v1_router)

# 6. Mount Static HTML Frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# 7. Database and Telemetry startup hooks
@app.on_event("startup")
def startup_event():
    # Database Initialization & Seeding
    from database.seed import seed_db
    try:
        seed_db()
    except Exception as e:
        print(f"Startup warning: Database seeding failed: {e}")
        
    # Start Background Telemetry Collection Loop
    from telemetry.collector import run_network_telemetry_loop
    asyncio.create_task(run_network_telemetry_loop())
    print("NOC Telemetry sweep engine launched successfully.")

# 8. Wrap FastAPI app with Socket.IO ASGI app
import socketio
from websocket import sio
app_asgi = socketio.ASGIApp(sio, other_asgi_app=app, socketio_path="socket.io")
