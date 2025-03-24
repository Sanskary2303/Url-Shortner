from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from datetime import datetime

class URLBase(BaseModel):
    original_url: HttpUrl

class URLCreate(URLBase):
    alias: Optional[str] = None
    expires_in_days: Optional[int] = None

class URLResponse(URLBase):
    short_code: str
    short_url: str
    expires_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

class URLStats(BaseModel):
    original_url: str
    short_code: str
    clicks: int
    created_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class BulkURLCreate(BaseModel):
    urls: List[URLCreate]

class BulkURLResponse(BaseModel):
    urls: List[URLResponse]
    
    class Config:
        from_attributes = True

class URLUpdate(BaseModel):
    expires_in_days: Optional[int] = None
    
    class Config:
        from_attributes = True