"""
core/rate_limiter.py
--------------------
Centralized rate limiter configuration using slowapi.

Supports:
- IP-based rate limiting (key_func = get_remote_address)
- Redis backend storage with automatic fallback to in-memory (memory://) if Redis is down
- Global defaults loaded from config settings
"""
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from api.config import settings

logger = logging.getLogger("noc.api")

# Determine storage URI based on Redis availability
storage_uri = "memory://"
try:
    from services.redis_cache import RedisCacheManager
    if RedisCacheManager.ping():
        storage_uri = settings.REDIS_URL
        logger.info("Rate limiter using Redis storage backend", extra={"url": settings.REDIS_URL})
    else:
        logger.info("Rate limiter falling back to local in-memory storage (Redis is unreachable)")
except Exception as e:
    logger.warning(f"Error checking Redis backend for rate limiter: {e}. Defaulting to in-memory.")

# Initialize the global Limiter
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=storage_uri,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"]
)
