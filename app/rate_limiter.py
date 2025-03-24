from fastapi import HTTPException, Request
from .cache import redis_client
import os

RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "True").lower() in ("true", "1", "t")
MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))

async def rate_limiter(request: Request):
    """
    Rate limiting middleware to prevent abuse
    """
    if not RATE_LIMIT_ENABLED:
        return
        
    client_ip = request.client.host if request.client else "unknown"
    
    endpoint = request.url.path
    rate_limit_key = f"rate_limit:{client_ip}:{endpoint}"
    
    current_count = redis_client.get(rate_limit_key)
    
    if current_count is None:
        redis_client.setex(rate_limit_key, RATE_LIMIT_WINDOW, 1)
    else:
        current_count = int(current_count)
        
        if current_count >= MAX_REQUESTS:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Try again later."
            )
            
        redis_client.incr(rate_limit_key)