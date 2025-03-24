from fastapi import FastAPI, HTTPException, Depends, Request, Response, status
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from . import models, schemas, utils
from .database import engine, get_db
import validators
from datetime import datetime, timedelta
import os
from . import cache
from .cache import redis_client
from fastapi import BackgroundTasks
from .rate_limiter import rate_limiter
from .auth import get_api_key
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from .logger import log_url_created, log_url_accessed, log_error
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from .logger import log_error
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response, HTTPException
import json
from .key_rotation import KeyRotationManager
from pydantic import BaseModel
from typing import Optional

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="URL Shortener API",
    description="A URL shortening service API with rate limiting, security, and tracking features",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .middlewares import TimingMiddleware
app.add_middleware(TimingMiddleware)

app.mount("/ui", StaticFiles(directory="static", html=True), name="static")

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

class RequestSizeLimiter(BaseHTTPMiddleware):
    def __init__(
        self, 
        app, 
        max_content_length_bytes: int = 1024 * 1024
    ):
        super().__init__(app)
        self.max_content_length_bytes = max_content_length_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get('content-length')
        
        if content_length:
            content_length = int(content_length)
            if content_length > self.max_content_length_bytes:
                return Response(
                    status_code=413,
                    content=json.dumps({
                        "detail": f"Request body too large. Maximum allowed size is {self.max_content_length_bytes} bytes."
                    }),
                    media_type="application/json"
                )
        
        return await call_next(request)

app.add_middleware(RequestSizeLimiter, max_content_length_bytes=1024 * 1024)  # 1MB limit

@app.post("/shorten", response_model=schemas.URLResponse, dependencies=[Depends(rate_limiter)])
def create_short_url(url_data: schemas.URLCreate, db: Session = Depends(get_db)):
    """
    Create a shortened URL
    
    - **original_url**: The URL to shorten (must be a valid URL)
    - **alias**: Optional custom alias for the shortened URL
    - **expires_in_days**: Optional number of days until the link expires
    
    Returns a shortened URL and associated metadata
    """
    
    if not validators.url(str(url_data.original_url)):
        raise HTTPException(status_code=400, detail="Invalid URL provided")
    
    original_url = str(url_data.original_url)
    
    if url_data.alias:
        if not url_data.alias.isalnum():
            raise HTTPException(
                status_code=400, 
                detail="Alias can only contain alphanumeric characters"
            )
            
        existing_url = db.query(models.URLMapping).filter(
            models.URLMapping.short_code == url_data.alias
        ).first()
        
        if existing_url:
            raise HTTPException(
                status_code=400, 
                detail="Custom alias already in use"
            )
            
        short_code = url_data.alias
    else:
        existing_url = db.query(models.URLMapping).filter(
            models.URLMapping.original_url == original_url,
            (models.URLMapping.expires_at.is_(None) | (models.URLMapping.expires_at > datetime.utcnow()))
        ).first()
        
        if existing_url:
            return {
                "original_url": existing_url.original_url,
                "short_code": existing_url.short_code,
                "short_url": f"{BASE_URL}/{existing_url.short_code}",
                "expires_at": existing_url.expires_at,
                "created_at": existing_url.created_at
            }
            
        short_code = utils.generate_short_code(original_url)
        
        while db.query(models.URLMapping).filter(
            models.URLMapping.short_code == short_code
        ).first():
            short_code = utils.generate_random_code()
    
    expires_at = None
    if url_data.expires_in_days:
        expires_at = utils.calculate_expiry_date(url_data.expires_in_days)
    
    url_mapping = models.URLMapping(
        original_url=original_url,
        short_code=short_code,
        expires_at=expires_at
    )
    
    db.add(url_mapping)
    db.commit()
    db.refresh(url_mapping)
    
    log_url_created(short_code, original_url)
    
    return {
        "original_url": url_mapping.original_url,
        "short_code": url_mapping.short_code,
        "short_url": f"{BASE_URL}/{url_mapping.short_code}",
        "expires_at": url_mapping.expires_at,
        "created_at": url_mapping.created_at
    }

@app.post("/bulk-shorten", response_model=schemas.BulkURLResponse, dependencies=[Depends(rate_limiter), Depends(get_api_key)])
def create_bulk_short_urls(urls_data: schemas.BulkURLCreate, db: Session = Depends(get_db)):
    """
    Create multiple shortened URLs in a single request
    
    - **urls**: List of URLs to shorten with optional alias and expiry settings
    
    Returns a list of shortened URLs and their metadata
    
    Note: This endpoint requires API key authentication
    """
    results = []
    
    for url_data in urls_data.urls:
        if not validators.url(str(url_data.original_url)):
            continue
        
        original_url = str(url_data.original_url)
        
        if url_data.alias:
            if not url_data.alias.isalnum():
                continue
                
            existing_url = db.query(models.URLMapping).filter(
                models.URLMapping.short_code == url_data.alias
            ).first()
            
            if existing_url:
                continue
                
            short_code = url_data.alias
        else:
            existing_url = db.query(models.URLMapping).filter(
                models.URLMapping.original_url == original_url,
                (models.URLMapping.expires_at.is_(None) | (models.URLMapping.expires_at > datetime.utcnow()))
            ).first()
            
            if existing_url:
                results.append({
                    "original_url": existing_url.original_url,
                    "short_code": existing_url.short_code,
                    "short_url": f"{BASE_URL}/{existing_url.short_code}",
                    "expires_at": existing_url.expires_at,
                    "created_at": existing_url.created_at
                })
                continue
                
            short_code = utils.generate_short_code(original_url)
            
            while db.query(models.URLMapping).filter(
                models.URLMapping.short_code == short_code
            ).first():
                short_code = utils.generate_random_code()
        
        expires_at = None
        if url_data.expires_in_days:
            expires_at = utils.calculate_expiry_date(url_data.expires_in_days)
        
        url_mapping = models.URLMapping(
            original_url=original_url,
            short_code=short_code,
            expires_at=expires_at
        )
        
        db.add(url_mapping)
        db.commit()
        db.refresh(url_mapping)
        
        results.append({
            "original_url": url_mapping.original_url,
            "short_code": url_mapping.short_code,
            "short_url": f"{BASE_URL}/{url_mapping.short_code}",
            "expires_at": url_mapping.expires_at,
            "created_at": url_mapping.created_at
        })
    
    return {"urls": results}

@app.get("/{short_code}", dependencies=[Depends(rate_limiter)])
def redirect_to_url(
    short_code: str, 
    request: Request, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Redirect to the original URL using the short code
    
    - **short_code**: The code part of the shortened URL
    
    Redirects to the original URL and tracks click statistics
    """
    
    try:
        cached_url = cache.get_url_from_cache(short_code)
        if cached_url:
            background_tasks.add_task(
                update_url_stats, 
                short_code, 
                request, 
                db
            )
            log_url_accessed(short_code)
            return RedirectResponse(url=cached_url["original_url"])
        
        url_mapping = db.query(models.URLMapping).filter(
            models.URLMapping.short_code == short_code
        ).first()
        
        if not url_mapping:
            raise HTTPException(status_code=404, detail="URL not found")
        
        if url_mapping.expires_at and url_mapping.expires_at < datetime.utcnow():
            raise HTTPException(status_code=410, detail="URL has expired")
        
        url_mapping.clicks += 1
        
        cache_data = {
            "original_url": url_mapping.original_url,
            "short_code": url_mapping.short_code
        }
        
        if url_mapping.expires_at:
            ttl = (url_mapping.expires_at - datetime.utcnow()).total_seconds()
            cache.cache_url(short_code, cache_data, int(ttl))
        else:
            cache.cache_url(short_code, cache_data)
        
        statistics = models.URLStatistics(
            url_mapping_id=url_mapping.id,
            referrer=request.headers.get("referer"),
            user_agent=request.headers.get("user-agent"),
            ip_address=utils.anonymize_ip(request.client.host if request.client else None)
        )
        
        db.add(statistics)
        db.commit()
        
        log_url_accessed(short_code)
        
        return RedirectResponse(url=url_mapping.original_url)
    except Exception as e:
        log_error("Failed to process request", e)
        raise

def update_url_stats(short_code: str, request: Request, db: Session):
    """Update statistics for a URL access in the background"""
    url_mapping = db.query(models.URLMapping).filter(
        models.URLMapping.short_code == short_code
    ).first()
    
    if url_mapping:
        url_mapping.clicks += 1
        
        statistics = models.URLStatistics(
            url_mapping_id=url_mapping.id,
            referrer=request.headers.get("referer"),
            user_agent=request.headers.get("user-agent"),
            ip_address=utils.anonymize_ip(request.client.host if request.client else None)
        )
        
        db.add(statistics)
        db.commit()

@app.put("/{short_code}", response_model=schemas.URLResponse, dependencies=[Depends(rate_limiter), Depends(get_api_key)])
def update_url(
    short_code: str, 
    url_data: schemas.URLUpdate, 
    db: Session = Depends(get_db)
):
    """
    Update an existing shortened URL
    
    - **short_code**: The code of the shortened URL to update
    - **expires_in_days**: New expiration period in days (optional)
    
    Returns the updated URL data
    
    Note: This endpoint requires API key authentication
    """
    url_mapping = db.query(models.URLMapping).filter(
        models.URLMapping.short_code == short_code
    ).first()
    
    if not url_mapping:
        raise HTTPException(status_code=404, detail="URL not found")
    
    if url_data.expires_in_days is not None:
        url_mapping.expires_at = utils.calculate_expiry_date(url_data.expires_in_days)
        
        if url_mapping.expires_at:
            cache_data = {
                "original_url": url_mapping.original_url,
                "short_code": url_mapping.short_code
            }
            ttl = (url_mapping.expires_at - datetime.utcnow()).total_seconds()
            if ttl > 0:
                cache.cache_url(short_code, cache_data, int(ttl))
            else:
                cache.invalidate_url_cache(short_code)
        else:
            cache_data = {
                "original_url": url_mapping.original_url,
                "short_code": url_mapping.short_code
            }
            cache.cache_url(short_code, cache_data)
    
    db.commit()
    db.refresh(url_mapping)
    
    return {
        "original_url": url_mapping.original_url,
        "short_code": url_mapping.short_code,
        "short_url": f"{BASE_URL}/{url_mapping.short_code}",
        "expires_at": url_mapping.expires_at,
        "created_at": url_mapping.created_at
    }

@app.get("/stats/{short_code}", response_model=schemas.URLStats, dependencies=[Depends(rate_limiter), Depends(get_api_key)])
def get_url_stats(short_code: str, db: Session = Depends(get_db)):
    """
    Get statistics for a shortened URL
    
    - **short_code**: The code of the shortened URL
    
    Returns statistics about the URL including click count
    
    Note: This endpoint requires API key authentication
    """
    
    url_mapping = db.query(models.URLMapping).filter(
        models.URLMapping.short_code == short_code
    ).first()
    
    if not url_mapping:
        raise HTTPException(status_code=404, detail="URL not found")
    
    return {
        "original_url": url_mapping.original_url,
        "short_code": url_mapping.short_code,
        "clicks": url_mapping.clicks,
        "created_at": url_mapping.created_at,
        "expires_at": url_mapping.expires_at
    }

@app.delete("/{short_code}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(rate_limiter), Depends(get_api_key)])
def delete_url(short_code: str, db: Session = Depends(get_db)):
    """
    Delete a shortened URL
    
    - **short_code**: The code of the shortened URL to delete
    
    Returns no content on success
    
    Note: This endpoint requires API key authentication
    """
    
    url_mapping = db.query(models.URLMapping).filter(
        models.URLMapping.short_code == short_code
    ).first()
    
    if not url_mapping:
        raise HTTPException(status_code=404, detail="URL not found")
    
    db.delete(url_mapping)
    db.commit()
    
    cache.invalidate_url_cache(short_code)
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@app.get("/health", tags=["Health"])
def health_check():
    """
    Health check endpoint
    
    Returns the status of the service and its dependencies
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": app.version,
    }
    
    try:
        with engine.connect() as connection:
            result = connection.execute("SELECT 1")
            result.scalar()
        health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = "error"
        health_status["database_error"] = str(e)
        health_status["status"] = "unhealthy"
    
    try:
        redis_client.ping()
        health_status["cache"] = "connected"
    except Exception as e:
        health_status["cache"] = "error"
        health_status["cache_error"] = str(e)
        health_status["status"] = "unhealthy"
    
    return health_status

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="URL Shortener API",
        version="1.1.0",
        description="""
        # URL Shortener API
        
        This API provides services for shortening URLs, managing shortened URLs, and tracking click statistics.
        
        ## Features
        
        * Create shortened URLs with optional custom aliases
        * Bulk URL creation
        * Set expiration dates for URLs
        * Track click statistics
        * Update and delete URLs
        
        ## Security
        
        Most management endpoints require API key authentication. Set the `X-API-Key` header with your API key.
        Rate limiting is applied to prevent abuse.
        """,
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    log_error(f"HTTP error: {exc.detail}", error=exc, status_code=exc.status_code, path=request.url.path)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    log_error("Validation error", error=exc, path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc)},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    log_error("Unexpected error", error=exc, path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )

@app.get("/admin/urls", dependencies=[Depends(rate_limiter), Depends(get_api_key)])
def get_all_urls(
    active_only: bool = False,
    skip: int = 0, 
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get all URLs with optional filtering
    
    - **active_only**: If true, only return non-expired URLs
    - **skip**: Number of records to skip (for pagination)
    - **limit**: Maximum number of records to return
    
    Returns a list of URLs and counts
    
    Note: This endpoint requires API key authentication
    """
    total_count = db.query(func.count(models.URLMapping.id)).scalar()
    
    active_query = db.query(func.count(models.URLMapping.id))
    if active_only:
        active_query = active_query.filter(
            (models.URLMapping.expires_at.is_(None)) | 
            (models.URLMapping.expires_at > datetime.utcnow())
        )
    active_count = active_query.scalar()
    
    query = db.query(models.URLMapping)
    if active_only:
        query = query.filter(
            (models.URLMapping.expires_at.is_(None)) | 
            (models.URLMapping.expires_at > datetime.utcnow())
        )
    
    urls = query.order_by(models.URLMapping.created_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "total_count": total_count,
        "active_count": active_count,
        "urls": [
            {
                "short_code": url.short_code,
                "original_url": url.original_url,
                "short_url": f"{BASE_URL}/{url.short_code}",
                "clicks": url.clicks,
                "created_at": url.created_at,
                "expires_at": url.expires_at,
                "is_active": url.expires_at is None or url.expires_at > datetime.utcnow()
            }
            for url in urls
        ]
    }

class APIKeyCreate(BaseModel):
    description: str
    expires_in_days: Optional[int] = 90

class APIKeyResponse(BaseModel):
    key: str
    expires_at: datetime

@app.post("/admin/api-keys", response_model=APIKeyResponse, dependencies=[Depends(get_api_key)])
def create_api_key(key_data: APIKeyCreate, db: Session = Depends(get_db)):
    """
    Create a new API key
    
    - **description**: Description of the key's purpose
    - **expires_in_days**: Days until key expiration
    
    Returns the new API key (store it securely as it won't be shown again)
    
    Note: This endpoint requires API key authentication
    """
    new_key = KeyRotationManager.create_new_key(
        key_data.description, 
        key_data.expires_in_days
    )
    
    if not new_key:
        raise HTTPException(status_code=500, detail="Failed to create API key")
    
    expires_at = datetime.utcnow() + timedelta(days=key_data.expires_in_days)
    
    return {
        "key": new_key,
        "expires_at": expires_at
    }