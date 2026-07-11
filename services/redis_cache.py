import redis
import json
import logging
from typing import Optional
from api.config import settings

logger = logging.getLogger("redis_service")

class RedisCacheManager:
    _client = None
    _failed_previously = False
    _fallback_db = {}      # In-memory dictionary fallback
    _fallback_queues = {}  # In-memory list fallback
    _fallback_hashes = {}  # In-memory hash fallback
    
    @classmethod
    def get_client(cls):
        if cls._client is not None:
            return cls._client
            
        if cls._failed_previously:
            return None
            
        try:
            # Short socket timeouts so we don't block start-up if Redis is missing
            cls._client = redis.from_url(
                settings.REDIS_URL, 
                decode_responses=True, 
                socket_timeout=0.5,
                socket_connect_timeout=0.5
            )
            cls._client.ping()
            cls._failed_previously = False
            print("[REDIS] Connected successfully to Redis server.")
        except Exception as e:
            cls._client = None
            cls._failed_previously = True
            logger.warning(f"[REDIS] Redis is down or unreachable. Falling back to in-memory data structures. Info: {e}")
        return cls._client

    @classmethod
    def ping(cls) -> bool:
        client = cls.get_client()
        if client:
            try:
                return client.ping()
            except Exception:
                pass
        return False

    @classmethod
    def set(cls, key: str, value: str, ex: int = None) -> bool:
        client = cls.get_client()
        if client:
            try:
                client.set(key, value, ex=ex)
                return True
            except Exception:
                pass
        cls._fallback_db[key] = value
        return True

    @classmethod
    def get(cls, key: str) -> Optional[str]:
        client = cls.get_client()
        if client:
            try:
                return client.get(key)
            except Exception:
                pass
        return cls._fallback_db.get(key)

    @classmethod
    def delete(cls, key: str) -> bool:
        client = cls.get_client()
        if client:
            try:
                client.delete(key)
                return True
            except Exception:
                pass
        cls._fallback_db.pop(key, None)
        return True

    @classmethod
    def lpush(cls, key: str, value: str) -> int:
        client = cls.get_client()
        if client:
            try:
                return client.lpush(key, value)
            except Exception:
                pass
        if key not in cls._fallback_queues:
            cls._fallback_queues[key] = []
        cls._fallback_queues[key].insert(0, value)
        return len(cls._fallback_queues[key])

    @classmethod
    def rpop(cls, key: str) -> Optional[str]:
        client = cls.get_client()
        if client:
            try:
                return client.rpop(key)
            except Exception:
                pass
        if key in cls._fallback_queues and len(cls._fallback_queues[key]) > 0:
            return cls._fallback_queues[key].pop()
        return None

    @classmethod
    def llen(cls, key: str) -> int:
        client = cls.get_client()
        if client:
            try:
                return client.llen(key)
            except Exception:
                pass
        return len(cls._fallback_queues.get(key, []))

    @classmethod
    def hset(cls, key: str, mapping: dict) -> bool:
        client = cls.get_client()
        if client:
            try:
                client.hset(key, mapping=mapping)
                return True
            except Exception:
                pass
        if key not in cls._fallback_hashes:
            cls._fallback_hashes[key] = {}
        cls._fallback_hashes[key].update(mapping)
        return True

    @classmethod
    def hgetall(cls, key: str) -> dict:
        client = cls.get_client()
        if client:
            try:
                return client.hgetall(key)
            except Exception:
                pass
        return cls._fallback_hashes.get(key, {})

    @classmethod
    def hget(cls, key: str, field: str) -> Optional[str]:
        client = cls.get_client()
        if client:
            try:
                return client.hget(key, field)
            except Exception:
                pass
        return cls._fallback_hashes.get(key, {}).get(field)

    @classmethod
    def hdel(cls, key: str, *fields: str) -> int:
        client = cls.get_client()
        if client:
            try:
                return client.hdel(key, *fields)
            except Exception:
                pass
        count = 0
        h = cls._fallback_hashes.get(key, {})
        for f in fields:
            if f in h:
                del h[f]
                count += 1
        return count
