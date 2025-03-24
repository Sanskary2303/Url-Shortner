import time
from fastapi import Request, Depends, HTTPException, status
from .cache import redis_client, is_redis_available
from .logger import log_error
import os
import redis

RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "True").lower() in ("true", "1", "t")
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))

async def rate_limiter(request: Request):
    """
    Rate limiting middleware to prevent abuse
    """
    if not RATE_LIMIT_ENABLED:
        return
        
    if request.url.path.startswith("/static") or request.url.path.startswith("/ui"):
        return
        
    client_ip = request.client.host
    rate_limit_key = f"ratelimit:{client_ip}:{request.url.path}"
    
    try:
        if not is_redis_available():
            log_error("Rate limiting disabled - Redis unavailable")
            return
            
        current_count = redis_client.get(rate_limit_key)
        current_count = int(current_count) if current_count else 0
        
        if current_count >= RATE_LIMIT_MAX_REQUESTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later."
            )
            
        pipe = redis_client.pipeline()
        pipe.incr(rate_limit_key)
        pipe.expire(rate_limit_key, RATE_LIMIT_WINDOW)
        pipe.execute()
        
    except redis.exceptions.AuthenticationError:
        log_error("Redis authentication error - Rate limiting disabled")
        return
    except Exception as e:
        log_error("Rate limiting error", error=e)
        return