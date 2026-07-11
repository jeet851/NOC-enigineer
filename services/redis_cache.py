"""
services/redis_cache.py
-----------------------
Shared Redis cache manager with automatic in-memory fallback.

Features:
- All keys are automatically namespaced with settings.REDIS_KEY_PREFIX (default: "NOC:")
  This prevents key collisions and simplifies Redis server inspection.
- Configurable socket/connect timeouts via settings (REDIS_SOCKET_TIMEOUT, REDIS_CONNECT_TIMEOUT)
- Graceful fallback to in-memory data structures when Redis is unavailable
- Singleton connection pool shared across the entire application
- reset() method for test isolation

Fallback behavior:
  When Redis is unavailable, all operations succeed using in-memory
  dictionaries and lists. This ensures the platform continues functioning
  even without a Redis server (development/testing mode).

Note: In-memory fallback does NOT support TTL expiry — keys persist until
      the process restarts. For production, Redis is strongly recommended.
"""
import redis
import logging
from typing import Optional
from api.config import settings

logger = logging.getLogger("noc.redis")


class RedisCacheManager:
    _client = None
    _failed_previously = False

    # In-memory fallback stores (used when Redis is unavailable)
    _fallback_db: dict = {}       # For string/scalar keys
    _fallback_queues: dict = {}   # For list operations (lpush/rpop)
    _fallback_hashes: dict = {}   # For hash operations (hset/hgetall)

    @classmethod
    def _prefixed(cls, key: str) -> str:
        """
        Prepends the namespace prefix to all keys.
        Ensures all NOC keys are grouped under settings.REDIS_KEY_PREFIX
        (default: "NOC:") on the Redis server.
        """
        prefix = settings.REDIS_KEY_PREFIX
        if not key.startswith(prefix):
            return f"{prefix}{key}"
        return key

    @classmethod
    def get_client(cls):
        """
        Returns the Redis client, creating it on first call.
        Falls back to None if Redis is unreachable.
        After the first failure, subsequent calls skip retry to avoid
        blocking the application on every Redis operation.
        """
        if cls._client is not None:
            return cls._client

        if cls._failed_previously:
            return None

        try:
            cls._client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
            )
            cls._client.ping()
            cls._failed_previously = False
            logger.info(
                "Redis connected successfully",
                extra={"url": settings.REDIS_URL, "prefix": settings.REDIS_KEY_PREFIX}
            )
        except Exception as e:
            cls._client = None
            cls._failed_previously = True
            logger.warning(
                "Redis unavailable — falling back to in-memory data structures",
                extra={"error": str(e)}
            )
        return cls._client

    @classmethod
    def ping(cls) -> bool:
        """Returns True if Redis is reachable."""
        client = cls.get_client()
        if client:
            try:
                return client.ping()
            except Exception:
                pass
        return False

    @classmethod
    def set(cls, key: str, value: str, ex: Optional[int] = None) -> bool:
        """
        Sets a string key-value pair with optional TTL (seconds).
        Falls back to in-memory dict if Redis unavailable.
        Note: In-memory fallback does NOT enforce TTL expiry.
        """
        prefixed = cls._prefixed(key)
        client = cls.get_client()
        if client:
            try:
                client.set(prefixed, value, ex=ex)
                return True
            except Exception:
                pass
        cls._fallback_db[prefixed] = value
        return True

    @classmethod
    def get(cls, key: str) -> Optional[str]:
        """Gets a string value by key, returns None if not found."""
        prefixed = cls._prefixed(key)
        client = cls.get_client()
        if client:
            try:
                return client.get(prefixed)
            except Exception:
                pass
        return cls._fallback_db.get(prefixed)

    @classmethod
    def delete(cls, key: str) -> bool:
        """Deletes a key from cache or in-memory fallback."""
        prefixed = cls._prefixed(key)
        client = cls.get_client()
        if client:
            try:
                client.delete(prefixed)
                return True
            except Exception:
                pass
        cls._fallback_db.pop(prefixed, None)
        return True

    @classmethod
    def lpush(cls, key: str, value: str) -> int:
        """Pushes a value to the head of a Redis list."""
        prefixed = cls._prefixed(key)
        client = cls.get_client()
        if client:
            try:
                return client.lpush(prefixed, value)
            except Exception:
                pass
        if prefixed not in cls._fallback_queues:
            cls._fallback_queues[prefixed] = []
        cls._fallback_queues[prefixed].insert(0, value)
        return len(cls._fallback_queues[prefixed])

    @classmethod
    def rpop(cls, key: str) -> Optional[str]:
        """Pops a value from the tail of a Redis list."""
        prefixed = cls._prefixed(key)
        client = cls.get_client()
        if client:
            try:
                return client.rpop(prefixed)
            except Exception:
                pass
        if prefixed in cls._fallback_queues and cls._fallback_queues[prefixed]:
            return cls._fallback_queues[prefixed].pop()
        return None

    @classmethod
    def llen(cls, key: str) -> int:
        """Returns the length of a Redis list."""
        prefixed = cls._prefixed(key)
        client = cls.get_client()
        if client:
            try:
                return client.llen(prefixed)
            except Exception:
                pass
        return len(cls._fallback_queues.get(prefixed, []))

    @classmethod
    def hset(cls, key: str, mapping: dict) -> bool:
        """Sets multiple fields in a Redis hash."""
        prefixed = cls._prefixed(key)
        client = cls.get_client()
        if client:
            try:
                client.hset(prefixed, mapping=mapping)
                return True
            except Exception:
                pass
        if prefixed not in cls._fallback_hashes:
            cls._fallback_hashes[prefixed] = {}
        cls._fallback_hashes[prefixed].update(mapping)
        return True

    @classmethod
    def hgetall(cls, key: str) -> dict:
        """Returns all fields and values in a Redis hash."""
        prefixed = cls._prefixed(key)
        client = cls.get_client()
        if client:
            try:
                return client.hgetall(prefixed)
            except Exception:
                pass
        return cls._fallback_hashes.get(prefixed, {})

    @classmethod
    def hget(cls, key: str, field: str) -> Optional[str]:
        """Gets a single field from a Redis hash."""
        prefixed = cls._prefixed(key)
        client = cls.get_client()
        if client:
            try:
                return client.hget(prefixed, field)
            except Exception:
                pass
        return cls._fallback_hashes.get(prefixed, {}).get(field)

    @classmethod
    def hdel(cls, key: str, *fields: str) -> int:
        """Deletes fields from a Redis hash."""
        prefixed = cls._prefixed(key)
        client = cls.get_client()
        if client:
            try:
                return client.hdel(prefixed, *fields)
            except Exception:
                pass
        count = 0
        h = cls._fallback_hashes.get(prefixed, {})
        for f in fields:
            if f in h:
                del h[f]
                count += 1
        return count

    @classmethod
    def reset(cls) -> None:
        """
        Resets the Redis client and all in-memory fallback stores.
        Intended for use in tests to ensure a clean state between test runs.
        """
        cls._client = None
        cls._failed_previously = False
        cls._fallback_db = {}
        cls._fallback_queues = {}
        cls._fallback_hashes = {}
