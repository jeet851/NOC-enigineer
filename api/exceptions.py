"""
api/exceptions.py
-----------------
Registers FastAPI exception handlers for both custom NOC domain exceptions
and standard HTTP exceptions.

Handlers are registered once at app startup via register_exception_handlers().
In production mode, stack traces are never returned in API responses —
they are logged internally but stripped from client payloads.

Custom exceptions from core/exceptions.py are mapped to structured
StandardResponse-compatible JSON payloads.
"""
import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from core.exceptions import (
    NocBaseException,
    AuthenticationException,
    MFAException,
    AuthorizationException,
    TokenException,
    ValidationException,
    InjectionException,
    AutomationException,
    DeviceNotFoundException,
    CommandValidationException,
    TelemetryException,
    AIException,
    AIUnavailableException,
    DatabaseException,
    RecordNotFoundException,
    ConfigurationException,
    VaultException,
    RateLimitException,
)

logger = logging.getLogger("noc.api")


def _is_production() -> bool:
    """Returns True if the application is running in production mode."""
    try:
        from api.config import settings
        return settings.APP_ENV == "production"
    except Exception:
        return False


def _error_response(status_code: int, code: str, message: str, detail=None) -> JSONResponse:
    """Constructs a StandardResponse-compatible error payload."""
    body = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        }
    }
    # Only include detail in non-production environments
    if detail and not _is_production():
        body["error"]["detail"] = detail
    return JSONResponse(status_code=status_code, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    """
    Registers all custom and standard exception handlers on the FastAPI app.
    Call this once in api/app.py during application setup.
    """

    # ── NOC Domain Base (catches any NocBaseException subclass) ──────────────
    @app.exception_handler(NocBaseException)
    async def noc_base_exception_handler(request: Request, exc: NocBaseException):
        logger.warning(
            f"Domain exception [{exc.error_code}]: {exc.message}",
            extra={"path": request.url.path, "code": exc.error_code}
        )
        return _error_response(exc.status_code, exc.error_code, exc.message, exc.detail)

    # ── Authentication & Authorization ────────────────────────────────────────
    @app.exception_handler(AuthenticationException)
    async def authentication_exception_handler(request: Request, exc: AuthenticationException):
        logger.warning(
            f"Authentication failure: {exc.message}",
            extra={"path": request.url.path, "ip": request.client.host if request.client else "unknown"}
        )
        return _error_response(401, exc.error_code, exc.message)

    @app.exception_handler(AuthorizationException)
    async def authorization_exception_handler(request: Request, exc: AuthorizationException):
        logger.warning(
            f"Authorization denied: {exc.message}",
            extra={"path": request.url.path}
        )
        return _error_response(403, exc.error_code, exc.message)

    # ── Not Found ─────────────────────────────────────────────────────────────
    @app.exception_handler(RecordNotFoundException)
    async def record_not_found_handler(request: Request, exc: RecordNotFoundException):
        return _error_response(404, exc.error_code, exc.message)

    @app.exception_handler(DeviceNotFoundException)
    async def device_not_found_handler(request: Request, exc: DeviceNotFoundException):
        return _error_response(404, exc.error_code, exc.message)

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    @app.exception_handler(RateLimitException)
    async def rate_limit_exception_handler(request: Request, exc: RateLimitException):
        logger.warning(
            f"Rate limit exceeded: {request.url.path}",
            extra={"ip": request.client.host if request.client else "unknown"}
        )
        return _error_response(429, "RATE_LIMIT_EXCEEDED", "Too many requests. Please slow down.")

    # ── Pydantic Validation Errors ────────────────────────────────────────────
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        logger.warning(
            f"Request validation failed: {request.url.path}",
            extra={"errors": str(exc.errors())}
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request body or query parameter validation failed.",
                    "detail": exc.errors() if not _is_production() else None,
                }
            }
        )

    # ── Standard Python Exceptions ────────────────────────────────────────────
    @app.exception_handler(PermissionError)
    async def permission_error_handler(request: Request, exc: PermissionError):
        logger.warning(f"Permission denied on {request.url.path}: {str(exc)}")
        return _error_response(403, "PERMISSION_DENIED", str(exc))

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.warning(f"Value error on {request.url.path}: {str(exc)}")
        return _error_response(400, "BAD_REQUEST", str(exc))

    # ── Global Catch-All (last resort) ────────────────────────────────────────
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(
            f"Unhandled server error on {request.url.path}: {type(exc).__name__}: {str(exc)}",
            exc_info=True,
            extra={"path": request.url.path}
        )
        # Never expose internal details in production
        message = (
            f"Internal server error: {str(exc)}"
            if not _is_production()
            else "An internal server error occurred."
        )
        return _error_response(500, "INTERNAL_SERVER_ERROR", message)
