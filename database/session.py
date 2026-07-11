import os
import re
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from api.config import settings
from contextlib import asynccontextmanager, contextmanager

# Helper to map database URLs to their async driver equivalents
def get_async_db_url(url: str) -> str:
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    elif url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    elif url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    return url

# 1. Sync Database Configurations
sync_connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    sync_connect_args["check_same_thread"] = False

engine_kwargs = {
    "pool_pre_ping": settings.DB_POOL_PRE_PING,
    "connect_args": sync_connect_args
}
if not settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW

engine = create_engine(
    settings.DATABASE_URL,
    **engine_kwargs
)

# 2. Async Database Configurations
async_db_url = get_async_db_url(settings.DATABASE_URL)
async_connect_args = {}
if async_db_url.startswith("sqlite"):
    async_connect_args["check_same_thread"] = False

async_engine_kwargs = {
    "pool_pre_ping": settings.DB_POOL_PRE_PING,
    "connect_args": async_connect_args
}
if not async_db_url.startswith("sqlite"):
    async_engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    async_engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW

async_engine = create_async_engine(
    async_db_url,
    **async_engine_kwargs
)

# 3. SQLite Pragma optimizations
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if settings.DATABASE_URL.startswith("sqlite"):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=-10000")
            cursor.close()
        except Exception:
            pass

# 4. Session Factories
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

# 5. Context Managers for dependency injection and background tasks
@contextmanager
def get_db_context():
    """
    Context manager for synchronous database sessions (e.g., Celery, CLI).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@asynccontextmanager
async def get_async_db_context():
    """
    Context manager for asynchronous database sessions (e.g., background async tasks).
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
