import pytest
from services.redis_cache import RedisCacheManager

@pytest.fixture(autouse=True)
def force_fallback():
    # Force fallback state for predictable unit testing
    RedisCacheManager._client = None
    RedisCacheManager._failed_previously = True
    RedisCacheManager._fallback_db.clear()
    RedisCacheManager._fallback_queues.clear()
    RedisCacheManager._fallback_hashes.clear()
    yield

def test_redis_set_and_get():
    assert RedisCacheManager.set("test_key", "test_value") is True
    assert RedisCacheManager.get("test_key") == "test_value"
    assert RedisCacheManager.get("non_existent") is None

def test_redis_delete():
    RedisCacheManager.set("temp_key", "temp_val")
    assert RedisCacheManager.delete("temp_key") is True
    assert RedisCacheManager.get("temp_key") is None

def test_redis_list_operations():
    assert RedisCacheManager.lpush("my_list", "item1") == 1
    assert RedisCacheManager.lpush("my_list", "item2") == 2
    assert RedisCacheManager.llen("my_list") == 2
    
    assert RedisCacheManager.rpop("my_list") == "item1"
    assert RedisCacheManager.rpop("my_list") == "item2"
    assert RedisCacheManager.rpop("my_list") is None
    assert RedisCacheManager.llen("my_list") == 0

def test_redis_hash_operations():
    mapping = {"field1": "val1", "field2": "val2"}
    assert RedisCacheManager.hset("my_hash", mapping) is True
    
    assert RedisCacheManager.hget("my_hash", "field1") == "val1"
    assert RedisCacheManager.hgetall("my_hash") == mapping
    
    assert RedisCacheManager.hdel("my_hash", "field1") == 1
    assert RedisCacheManager.hget("my_hash", "field1") is None
    assert RedisCacheManager.hget("my_hash", "field2") == "val2"
