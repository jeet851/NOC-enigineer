"""
core/exceptions.py
------------------
Centralized custom exception hierarchy for the Zero-Trust AI NOC Copilot.

All domain-specific exceptions derive from NocBaseException so that
FastAPI's exception handlers can catch them in a single handler while
still returning structured, meaningful HTTP responses.

Usage:
    from core.exceptions import AuthenticationException
    raise AuthenticationException("Invalid OTP code")
"""
from typing import Optional, Any


class NocBaseException(Exception):
    """
    Base class for all NOC platform exceptions.
    Carries an optional HTTP status code and structured detail payload.
    """
    status_code: int = 500
    error_code: str = "NOC_ERROR"

    def __init__(
        self,
        message: str,
        detail: Optional[Any] = None,
        *,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code


# ─────────────────────────────────────────────────
# Authentication & Authorisation Exceptions
# ─────────────────────────────────────────────────

class AuthenticationException(NocBaseException):
    """Raised when authentication credentials are missing or invalid."""
    status_code = 401
    error_code = "AUTHENTICATION_FAILED"


class MFAException(NocBaseException):
    """Raised when a MFA/TOTP challenge fails or expires."""
    status_code = 401
    error_code = "MFA_FAILED"


class AuthorizationException(NocBaseException):
    """Raised when a user lacks the required RBAC permissions."""
    status_code = 403
    error_code = "AUTHORIZATION_DENIED"


class TokenException(NocBaseException):
    """Raised when a JWT or refresh token is invalid, expired, or revoked."""
    status_code = 401
    error_code = "TOKEN_INVALID"


# ─────────────────────────────────────────────────
# Input Validation Exceptions
# ─────────────────────────────────────────────────

class ValidationException(NocBaseException):
    """Raised when request payload fails business logic validation."""
    status_code = 422
    error_code = "VALIDATION_ERROR"


class InjectionException(NocBaseException):
    """Raised when prompt injection or command injection is detected."""
    status_code = 400
    error_code = "INJECTION_DETECTED"


# ─────────────────────────────────────────────────
# Device Automation Exceptions
# ─────────────────────────────────────────────────

class AutomationException(NocBaseException):
    """Raised when a device automation task fails."""
    status_code = 500
    error_code = "AUTOMATION_FAILED"


class DeviceNotFoundException(NocBaseException):
    """Raised when a target device is not found in the NOC inventory."""
    status_code = 404
    error_code = "DEVICE_NOT_FOUND"


class CommandValidationException(NocBaseException):
    """Raised when a configuration command fails safety/syntax validation."""
    status_code = 400
    error_code = "COMMAND_VALIDATION_FAILED"


# ─────────────────────────────────────────────────
# Telemetry Exceptions
# ─────────────────────────────────────────────────

class TelemetryException(NocBaseException):
    """Raised when a telemetry collection or parsing operation fails."""
    status_code = 500
    error_code = "TELEMETRY_ERROR"


# ─────────────────────────────────────────────────
# AI / LLM Exceptions
# ─────────────────────────────────────────────────

class AIException(NocBaseException):
    """Raised when a Gemini or other LLM call fails."""
    status_code = 503
    error_code = "AI_SERVICE_ERROR"


class AIUnavailableException(NocBaseException):
    """Raised when the AI backend is not configured (no API key)."""
    status_code = 503
    error_code = "AI_UNAVAILABLE"


# ─────────────────────────────────────────────────
# Database Exceptions
# ─────────────────────────────────────────────────

class DatabaseException(NocBaseException):
    """Raised when a database operation fails unexpectedly."""
    status_code = 500
    error_code = "DATABASE_ERROR"


class RecordNotFoundException(NocBaseException):
    """Raised when a requested record is not found in the database."""
    status_code = 404
    error_code = "RECORD_NOT_FOUND"


# ─────────────────────────────────────────────────
# Configuration Exceptions
# ─────────────────────────────────────────────────

class ConfigurationException(NocBaseException):
    """Raised when required configuration values are missing or invalid."""
    status_code = 500
    error_code = "CONFIGURATION_ERROR"


# ─────────────────────────────────────────────────
# Vault / Secret Exceptions
# ─────────────────────────────────────────────────

class VaultException(NocBaseException):
    """Raised when a vault secret operation (encrypt/decrypt/read) fails."""
    status_code = 500
    error_code = "VAULT_ERROR"


# ─────────────────────────────────────────────────
# Rate Limiting Exceptions
# ─────────────────────────────────────────────────

class RateLimitException(NocBaseException):
    """Raised when request rate limits are exceeded."""
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
