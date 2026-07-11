"""
core/logger.py
--------------
Enterprise structured logging setup for the Zero-Trust AI NOC Copilot.

Features:
- JSON-formatted log records for structured log aggregation
- RotatingFileHandler with configurable size and backup count
- Separate named loggers per domain (auth, ai, telemetry, etc.)
- Request correlation ID support (X-Request-ID propagation)
- Environment-aware log levels
- Console + file output in all environments

Usage:
    # In application startup (called once in api/app.py):
    from core.logger import setup_logging
    setup_logging()

    # In any module:
    import logging
    logger = logging.getLogger("noc.telemetry")
    logger.info("Telemetry loop started", extra={"interval": 5})

Named loggers (use these for domain isolation):
    noc.api        — FastAPI requests / responses
    noc.auth       — Authentication / authorization events
    noc.ai         — AI engine / Gemini calls
    noc.telemetry  — Telemetry collection
    noc.incident   — Incident engine
    noc.automation — Device automation & SSH
    noc.celery     — Celery background workers
    noc.websocket  — Socket.IO events
    noc.redis      — Redis cache operations
    noc.vault      — Vault secret operations
    noc.security   — Security events (injection, blocked requests)
    noc.discovery  — Network discovery scanning
"""
import os
import sys
import json
import logging
import logging.handlers
from datetime import datetime, timezone
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# JSON Formatter
# ─────────────────────────────────────────────────────────────────────────────

class JsonFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects for structured log ingestion
    (e.g., ELK stack, Datadog, CloudWatch).
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Append extra fields passed via logger.info("msg", extra={...})
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in {
                "args", "created", "exc_info", "exc_text", "filename",
                "funcName", "id", "levelname", "levelno", "lineno",
                "message", "module", "msecs", "msg", "name", "pathname",
                "process", "processName", "relativeCreated", "stack_info",
                "taskName", "thread", "threadName",
            }
        }
        if extra_fields:
            log_entry["context"] = extra_fields

        # Exception details (never expose full traceback in production response,
        # but always write to logs)
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# Pretty Console Formatter (development only)
# ─────────────────────────────────────────────────────────────────────────────

class ConsoleFormatter(logging.Formatter):
    """Human-readable formatter for development console output."""

    COLORS = {
        "DEBUG":    "\033[36m",    # Cyan
        "INFO":     "\033[32m",    # Green
        "WARNING":  "\033[33m",    # Yellow
        "ERROR":    "\033[31m",    # Red
        "CRITICAL": "\033[35m",    # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        prefix = f"{color}[{record.levelname[:4]}]{self.RESET}"
        return f"{ts} {prefix} [{record.name}] {record.getMessage()}"


# ─────────────────────────────────────────────────────────────────────────────
# Setup Function
# ─────────────────────────────────────────────────────────────────────────────

def setup_logging() -> None:
    """
    Initializes the root logging configuration.
    Called once at application startup from api/app.py.

    Reads configuration from api.config.settings:
      LOG_LEVEL       — Minimum log level (default: INFO)
      LOG_DIR         — Directory for log files (default: logs/)
      LOG_FILE        — Log file name (default: noc_copilot.log)
      LOG_MAX_BYTES   — Max log file size before rotation (default: 10MB)
      LOG_BACKUP_COUNT — Number of rotated files to keep (default: 10)
      APP_ENV         — Environment (development uses pretty console output)
    """
    try:
        from api.config import settings
        log_level_str = settings.LOG_LEVEL.upper()
        log_dir = settings.LOG_DIR
        log_file = settings.LOG_FILE
        log_max_bytes = settings.LOG_MAX_BYTES
        log_backup_count = settings.LOG_BACKUP_COUNT
        app_env = settings.APP_ENV
    except Exception:
        # Fallback defaults if config hasn't loaded yet
        log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
        log_dir = os.environ.get("LOG_DIR", "logs")
        log_file = os.environ.get("LOG_FILE", "noc_copilot.log")
        log_max_bytes = 10_485_760
        log_backup_count = 10
        app_env = os.environ.get("APP_ENV", "development")

    log_level = getattr(logging, log_level_str, logging.INFO)

    root_logger = logging.getLogger()

    # Avoid adding duplicate handlers if called multiple times
    if root_logger.handlers:
        return

    root_logger.setLevel(log_level)

    # ── Console Handler ──────────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    if app_env == "development":
        # Human-readable output for local development
        console_handler.setFormatter(ConsoleFormatter())
    else:
        # JSON output for production (captured by log aggregators)
        console_handler.setFormatter(JsonFormatter())

    root_logger.addHandler(console_handler)

    # ── Rotating File Handler ────────────────────────────────────────────────
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, log_file)

        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_path,
            maxBytes=log_max_bytes,
            backupCount=log_backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(JsonFormatter())  # Always JSON in files
        root_logger.addHandler(file_handler)

    except Exception as e:
        # Non-fatal: file logging unavailable (e.g., permission denied in containers)
        root_logger.warning(f"Could not configure file logging: {e}")

    # ── Silence noisy third-party loggers ────────────────────────────────────
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # ── Startup confirmation ──────────────────────────────────────────────────
    startup_logger = logging.getLogger("noc.startup")
    startup_logger.info(
        "Logging system initialized",
        extra={
            "level": log_level_str,
            "log_dir": log_dir,
            "log_file": log_file,
            "env": app_env,
        }
    )


def get_logger(name: str) -> logging.Logger:
    """
    Convenience function to get a named NOC logger.
    Automatically prefixes with 'noc.' if not already present.

    Example:
        logger = get_logger("telemetry")  # → logging.getLogger("noc.telemetry")
    """
    if not name.startswith("noc."):
        name = f"noc.{name}"
    return logging.getLogger(name)
