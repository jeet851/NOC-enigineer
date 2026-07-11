import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    BIND_HOST: str = "127.0.0.1"
    PORT: int = 5001
    
    # Database and Brokers
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/noc_db"
    REDIS_URL: str = "redis://localhost:6379/0"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672//"
    
    # Security
    JWT_SECRET_KEY: str = "supersecretnocjwtkey2026_change_me_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Slack and AI
    SLACK_BOT_TOKEN: Optional[str] = None
    SLACK_APP_TOKEN: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    
    # SSL Paths
    SSL_CERT_PATH: str = "localhost.crt"
    SSL_KEY_PATH: str = "localhost.key"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
