"""
api/config.py
-------------
Centralized Pydantic Settings for the Zero-Trust AI NOC Copilot platform.

All configurable values live here. Never hardcode environment-specific
values in source code — load them via environment variables or .env file.

Environment loading precedence (highest to lowest):
  1. Actual environment variable
  2. .env file (loaded by pydantic-settings)
  3. Default value defined below

To use different environments:
  APP_ENV=development  → loads .env.development
  APP_ENV=testing      → loads .env.testing
  APP_ENV=production   → loads .env.production
"""
import os
from typing import Optional, List
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ─────────────────────────────────────────────────
    # Application Environment
    # ─────────────────────────────────────────────────
    APP_ENV: str = "development"            # development | testing | production
    DEBUG: bool = False                     # Enable debug mode (never True in production)
    APP_NAME: str = "Zero-Trust AI NOC Copilot"
    APP_VERSION: str = "2.0.0"

    # ─────────────────────────────────────────────────
    # Server / Network Binding
    # ─────────────────────────────────────────────────
    BIND_HOST: str = "127.0.0.1"
    PORT: int = 5001

    # ─────────────────────────────────────────────────
    # Database
    # ─────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./noc_local.db"
    DB_POOL_SIZE: int = 10                  # SQLAlchemy sync pool size
    DB_MAX_OVERFLOW: int = 20               # Max overflow connections above pool_size
    DB_POOL_PRE_PING: bool = True           # Verify connections before use

    # ─────────────────────────────────────────────────
    # Redis
    # ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_SOCKET_TIMEOUT: float = 0.5       # Socket read timeout in seconds
    REDIS_CONNECT_TIMEOUT: float = 0.5      # Socket connect timeout in seconds
    REDIS_KEY_PREFIX: str = "NOC:"          # Namespace prefix for all Redis keys
    REDIS_CACHE_TTL_SECONDS: int = 3        # Default cache TTL for telemetry data
    REDIS_CHALLENGE_TTL_SECONDS: int = 300  # MFA challenge expiry (5 minutes)
    REDIS_SESSION_TTL_SECONDS: int = 3600   # Session cache TTL (1 hour)

    # ─────────────────────────────────────────────────
    # RabbitMQ / Celery
    # ─────────────────────────────────────────────────
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672//"
    CELERY_TASK_ALWAYS_EAGER: bool = False  # Set True in testing to run tasks inline

    # ─────────────────────────────────────────────────
    # Security / JWT
    # ─────────────────────────────────────────────────
    # IMPORTANT: JWT_SECRET_KEY must be set to a strong random value in production.
    # It will fail startup validation if left as None in production.
    JWT_SECRET_KEY: str = "supersecretnocjwtkey2026_change_me_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ─────────────────────────────────────────────────
    # Rate Limiting
    # ─────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60         # Default API rate limit per IP per minute
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10    # Stricter limit for auth endpoints

    # ─────────────────────────────────────────────────
    # Logging
    # ─────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"                 # DEBUG | INFO | WARNING | ERROR | CRITICAL
    LOG_DIR: str = "logs"                   # Directory for log files (relative to CWD)
    LOG_FILE: str = "noc_copilot.log"       # Log file name
    LOG_MAX_BYTES: int = 10_485_760         # 10 MB max per log file
    LOG_BACKUP_COUNT: int = 10              # Keep 10 rotated log files

    # ─────────────────────────────────────────────────
    # Slack Integration
    # ─────────────────────────────────────────────────
    SLACK_BOT_TOKEN: Optional[str] = None
    SLACK_APP_TOKEN: Optional[str] = None

    # ─────────────────────────────────────────────────
    # Google Gemini AI
    # ─────────────────────────────────────────────────
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"  # Default Gemini model to use
    GEMINI_TIMEOUT_SECONDS: int = 30        # Timeout for Gemini API calls

    # ─────────────────────────────────────────────────
    # SSL / TLS
    # ─────────────────────────────────────────────────
    SSL_CERT_PATH: str = "localhost.crt"
    SSL_KEY_PATH: str = "localhost.key"

    # ─────────────────────────────────────────────────
    # Telemetry Collection
    # ─────────────────────────────────────────────────
    TELEMETRY_INTERVAL_SECONDS: int = 5     # How often the telemetry loop runs
    TELEMETRY_RETENTION_DAYS: int = 30      # How many days of telemetry to retain

    # ─────────────────────────────────────────────────
    # Automation / Device SSH
    # ─────────────────────────────────────────────────
    FORCE_SIMULATION: bool = True           # True = always use simulated CLI (sandbox mode)
    AUTOMATION_HISTORY_PATH: str = "automation_history.json"
    SSH_TIMEOUT_SECONDS: int = 10           # SSH connection timeout

    # ─────────────────────────────────────────────────
    # Neo4j Topology Graph (optional)
    # ─────────────────────────────────────────────────
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # ─────────────────────────────────────────────────
    # Vault
    # ─────────────────────────────────────────────────
    VAULT_KEY_FILE: str = "vault.key"
    VAULT_DATA_FILE: str = "vault_data.json"

    # ─────────────────────────────────────────────────
    # Alarm Thresholds
    # ─────────────────────────────────────────────────
    ALARM_CPU_THRESHOLD: int = 90           # CPU % to trigger alarm
    ALARM_RAM_THRESHOLD: int = 90           # RAM % to trigger alarm
    ALARM_DISK_THRESHOLD: int = 90          # Disk % to trigger alarm
    ALARM_PACKET_LOSS_THRESHOLD: float = 5.0  # Packet loss % to trigger alarm
    ALARM_RTT_THRESHOLD: float = 200.0      # Ping RTT ms to trigger alarm
    ALARM_TEMP_THRESHOLD: int = 75          # Temperature °C to trigger alarm

    # ─────────────────────────────────────────────────
    # AI Incident Engine
    # ─────────────────────────────────────────────────
    AI_CONFIDENCE_AUTONOMOUS_THRESHOLD: float = 95.0  # Confidence % for autonomous healing

    # ─────────────────────────────────────────────────
    # CORS
    # ─────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = ["*"]         # Restrict in production

    # ─────────────────────────────────────────────────
    # Pydantic Settings Config
    # ─────────────────────────────────────────────────
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ─────────────────────────────────────────────────
    # Startup Validation
    # ─────────────────────────────────────────────────
    @model_validator(mode="after")
    def validate_production_requirements(self) -> "Settings":
        """
        Enforces stricter configuration requirements in production mode.
        Raises ConfigurationException if critical settings are missing.
        """
        if self.APP_ENV == "production":
            from core.exceptions import ConfigurationException

            if not self.JWT_SECRET_KEY or self.JWT_SECRET_KEY == "supersecretnocjwtkey2026_change_me_in_production":
                raise ConfigurationException(
                    "JWT_SECRET_KEY must be set to a strong custom secret key in production environment. "
                    "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            if self.DATABASE_URL.startswith("sqlite"):
                import logging
                logging.getLogger("noc.config").warning(
                    "SQLite is not recommended for production. "
                    "Configure DATABASE_URL to use PostgreSQL."
                )
            if self.DEBUG:
                raise ConfigurationException(
                    "DEBUG=True is not allowed in production environment."
                )
        return self

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of: {valid_levels}")
        return upper

    @field_validator("APP_ENV")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        valid_envs = {"development", "testing", "production"}
        lower = v.lower()
        if lower not in valid_envs:
            raise ValueError(f"APP_ENV must be one of: {valid_envs}")
        return lower


# Singleton settings instance — import this everywhere
settings = Settings()
