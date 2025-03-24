import redis
import os
import json
from .logger import log_error

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "True").lower() in ("true", "1", "t")
CACHE_TTL = int(os.getenv("CACHE_TTL", 3600))

class DummyRedisClient:
    def get(self, key):
        return None
        
    def setex(self, key, ttl, value):
        pass
        
    def delete(self, key):
        pass
        
    def ping(self):
        return False

if REDIS_ENABLED:
    try:
        redis_client = redis.from_url(REDIS_URL)
        redis_client.ping()
    except Exception as e:
        log_error("Redis connection failed, using dummy client", error=e)
        redis_client = DummyRedisClient()
else:
    redis_client = DummyRedisClient()

def get_url_from_cache(short_code):
    """Retrieve URL from cache if it exists"""
    try:
        cached_data = redis_client.get(f"url:{short_code}")
        if cached_data:
            return json.loads(cached_data)
    except Exception as e:
        log_error("Cache error when getting data", error=e)
    return None

def cache_url(short_code, url_data, ttl=None):
    """Cache URL data with TTL"""
    try:
        if ttl is None:
            ttl = CACHE_TTL
        redis_client.setex(
            f"url:{short_code}", 
            ttl,
            json.dumps(url_data)
        )
    except Exception as e:
        log_error("Cache error when setting data", error=e)

def invalidate_url_cache(short_code):
    """Remove URL from cache"""
    try:
        redis_client.delete(f"url:{short_code}")
    except Exception as e:
        log_error("Cache error when invalidating", error=e)

def is_redis_available():
    try:
        return redis_client.ping()
    except:
        return False