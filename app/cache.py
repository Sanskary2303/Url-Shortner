import redis
import os
import json
from .logger import log_error

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = redis.from_url(REDIS_URL)

CACHE_TTL = int(os.getenv("CACHE_TTL", 3600))

def get_url_from_cache(short_code):
    """Retrieve URL from cache if it exists"""
    try:
        cached_data = redis_client.get(f"url:{short_code}")
        if cached_data:
            return json.loads(cached_data)
    except (redis.RedisError, json.JSONDecodeError) as e:
        log_error("cache_error", error=e)
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
    except (redis.RedisError, json.JSONDecodeError) as e:
        log_error("Cache error when setting data", error=e)

def invalidate_url_cache(short_code):
    """Remove URL from cache"""
    try:
        redis_client.delete(f"url:{short_code}")
    except redis.RedisError as e:
        log_error("Cache error when invalidating", error=e)
        
def is_redis_available():
    try:
        return redis_client.ping()
    except:
        return False