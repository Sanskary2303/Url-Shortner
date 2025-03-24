import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from .logger import logger

class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        logger.info(f"Request processed in {process_time:.4f} seconds")
        
        return response