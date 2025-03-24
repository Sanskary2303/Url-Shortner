import secrets
import string
import datetime
from typing import Optional
import os
from .database import engine, get_db, SessionLocal
from sqlalchemy import Column, Integer, String, DateTime, Boolean, func, create_engine
from sqlalchemy.ext.declarative import declarative_base
from .database import Base
from .secrets_manager import secrets_manager
from .logger import log_error
import hashlib

class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key_id = Column(String, unique=True, index=True)
    key_hash = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    is_primary = Column(Boolean, default=False)

class KeyRotationManager:
    @staticmethod
    def generate_api_key(length: int = 64) -> str:
        """Generate a secure API key"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    @staticmethod
    def hash_key(api_key: str) -> str:
        """Hash the API key for storage (in a real implementation, use a secure hashing algorithm)"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    @staticmethod
    def create_new_key(description: str, expires_in_days: int = 90) -> Optional[str]:
        """Create a new API key and store it"""
        db = SessionLocal()
        try:
            api_key = KeyRotationManager.generate_api_key()
            key_id = f"key_{secrets.token_hex(8)}"
            
            expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=expires_in_days)
            
            key_hash = KeyRotationManager.hash_key(api_key)
            db_key = APIKey(
                key_id=key_id,
                key_hash=key_hash,
                description=description,
                expires_at=expires_at,
                is_active=True,
                is_primary=False
            )
            db.add(db_key)
            db.commit()
            db.refresh(db_key)
            
            secrets_manager.store_api_key(key_id, api_key)
            
            return api_key
        except Exception as e:
            log_error("Failed to create new API key", e)
            db.rollback()
            return None
        finally:
            db.close()
    
    @staticmethod
    def validate_key(api_key: str) -> bool:
        """Validate if an API key is valid"""
        if not api_key:
            return False
            
        db = SessionLocal()
        try:
            key_hash = KeyRotationManager.hash_key(api_key)
            
            db_key = db.query(APIKey).filter(
                APIKey.key_hash == key_hash,
                APIKey.is_active == True,
                (APIKey.expires_at.is_(None) | (APIKey.expires_at > datetime.datetime.utcnow()))
            ).first()
            
            return db_key is not None
        except Exception as e:
            log_error("Failed to validate API key", e)
            return False
        finally:
            db.close()
    
    @staticmethod
    def rotate_primary_key() -> Optional[str]:
        """Rotate the primary API key"""
        db = SessionLocal()
        try:
            current_primary = db.query(APIKey).filter(
                APIKey.is_primary == True,
                APIKey.is_active == True
            ).first()
            
            new_key = KeyRotationManager.create_new_key("Primary API Key", 90)
            if not new_key:
                return None
                
            new_key_id = f"key_{secrets.token_hex(8)}"
            new_key_hash = KeyRotationManager.hash_key(new_key)
            
            new_primary = APIKey(
                key_id=new_key_id,
                key_hash=new_key_hash,
                description="Primary API Key",
                expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=90),
                is_active=True,
                is_primary=True
            )
            
            db.add(new_primary)
            
            if current_primary:
                current_primary.is_primary = False
                current_primary.expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=7)
            
            db.commit()
            
            os.environ["API_KEY"] = new_key
            
            secrets_manager.store_api_key("default", new_key)
            
            return new_key
        except Exception as e:
            log_error("Failed to rotate primary API key", e)
            db.rollback()
            return None
        finally:
            db.close()
    
    @staticmethod
    def revoke_key(key_id: str) -> bool:
        """Revoke an API key"""
        db = SessionLocal()
        try:
            db_key = db.query(APIKey).filter(APIKey.key_id == key_id).first()
            if not db_key:
                return False
                
            db_key.is_active = False
            db.commit()
            
            secrets_manager.delete_api_key(key_id)
            
            return True
        except Exception as e:
            log_error(f"Failed to revoke API key: {key_id}", e)
            db.rollback()
            return False
        finally:
            db.close()

Base.metadata.create_all(bind=engine)