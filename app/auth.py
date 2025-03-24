from fastapi import Security, HTTPException, status, Depends, Request
from fastapi.security.api_key import APIKeyHeader
import os
from typing import Optional
from .key_rotation import KeyRotationManager
from .secrets_manager import secrets_manager

API_KEY_NAME = "X-API-Key"
API_KEY_REQUIRED = os.getenv("API_KEY_REQUIRED", "False").lower() in ("true", "1", "t")

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(
    api_key_header: str = Security(api_key_header)
) -> Optional[str]:
    """
    Validate API key for protected endpoints
    """
    if not API_KEY_REQUIRED:
        return None
        
    if not api_key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
    
    # Validate the API key using the key rotation manager
    if not KeyRotationManager.validate_key(api_key_header):
        # Fallback to checking against the primary key in secrets manager/env
        primary_key = secrets_manager.get_api_key()
        if api_key_header != primary_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
    
    return api_key_header