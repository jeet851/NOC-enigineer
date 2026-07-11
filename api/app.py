import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from api.config import settings
from api.exceptions import register_exception_handlers
from core.logger import setup_logging
from core.rate_limiter import limiter
from slowapi.middleware import SlowAPIMiddleware

# Initialize structured JSON logging for the application
setup_logging()
logger = logging.getLogger("noc.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info("Initializing Zero-Trust AI NOC Server startup lifecycle hooks...")
    
    # Database Initialization & Seeding
    from database.seed import seed_db
    try:
        seed_db()
    except Exception as e:
        logger.error(f"Startup warning: Database seeding failed: {e}", exc_info=True)
        
    # Start Background Telemetry Collection Loop
    from telemetry.collector import run_network_telemetry_loop
    telemetry_task = asyncio.create_task(run_network_telemetry_loop())
    logger.info("NOC Telemetry sweep engine launched successfully.")
    
    yield
    
    # Shutdown actions
    logger.info("Cleaning up server resources during shutdown lifecycle hooks...")
    telemetry_task.cancel()
    try:
        await telemetry_task
    except asyncio.CancelledError:
        pass
    logger.info("NOC background telemetry task stopped. Cleanup complete.")


from routes import (
    auth, chat, action, settings as settings_routes, config,
    vault, audit, telemetry, health, reports, topology,
    diagnostics, discovery, incident, cli, packets,
    automation, knowledge_base, zero_trust, optimization,
    metrics
)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# Attach slowapi rate limiter to app state
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# 1. CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Zero-Trust Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Default permissive policy for development
    csp_policy = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        "img-src 'self' data:; "
        "connect-src 'self';"
    )
    
    # Hardened policy for production compliance (no unsafe-inline)
    if settings.APP_ENV == "production":
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
            "img-src 'self' data:; "
            "connect-src 'self';"
        )
        
    response.headers["Content-Security-Policy"] = csp_policy
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
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

# 7. Wrap FastAPI app with Socket.IO ASGI app
import socketio
from websocket import sio
app_asgi = socketio.ASGIApp(sio, other_asgi_app=app, socketio_path="socket.io")
