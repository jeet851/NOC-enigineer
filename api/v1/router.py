from fastapi import APIRouter
from fastapi.routing import APIRoute
from routes import (
    auth, chat, action, settings as settings_routes, config,
    vault, audit, telemetry, health, reports, topology,
    diagnostics, discovery, incident, cli, packets,
    automation, knowledge_base, zero_trust, optimization,
    metrics
)

v1_router = APIRouter(prefix="/api/v1")

routers_list = [
    auth.router, chat.router, action.router, settings_routes.router,
    config.router, vault.router, audit.router, telemetry.router,
    health.router, reports.router, topology.router, diagnostics.router,
    discovery.router, incident.router, cli.router, packets.router,
    automation.router, knowledge_base.router, zero_trust.router,
    optimization.router, metrics.router
]

for router in routers_list:
    for route in router.routes:
        if isinstance(route, APIRoute):
            # Strip '/api' from the prefix of the individual route path (e.g. /api/login -> /login)
            path = route.path
            if path.startswith("/api"):
                path = path.replace("/api", "", 1)
                
            # Register route under v1_router (prefix /api/v1)
            v1_router.add_api_route(
                path=path,
                endpoint=route.endpoint,
                response_model=route.response_model,
                status_code=route.status_code,
                tags=route.tags,
                dependencies=route.dependencies,
                summary=route.summary,
                description=route.description,
                response_description=route.response_description,
                responses=route.responses,
                deprecated=route.deprecated,
                methods=route.methods,
                operation_id=route.operation_id,
                response_model_include=route.response_model_include,
                response_model_exclude=route.response_model_exclude,
                response_model_by_alias=route.response_model_by_alias,
                response_model_exclude_unset=route.response_model_exclude_unset,
                response_model_exclude_defaults=route.response_model_exclude_defaults,
                response_model_exclude_none=route.response_model_exclude_none,
                include_in_schema=route.include_in_schema,
                response_class=route.response_class,
                name=route.name,
                callbacks=route.callbacks,
                openapi_extra=route.openapi_extra,
                generate_unique_id_function=route.generate_unique_id_function
            )
