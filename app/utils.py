import hashlib
import string
import random
import validators
from datetime import datetime, timedelta
import ipaddress
from datetime import datetime
from . import models

def generate_short_code(url: str, length: int = 7) -> str:
    """Generate a short code based on the URL"""
    hash_object = hashlib.md5(url.encode())
    hash_hex = hash_object.hexdigest()
    
    return hash_hex[:length]

def generate_random_code(length: int = 7) -> str:
    """Generate a random short code"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def is_valid_url(url: str) -> bool:
    """Validate if a string is a valid URL"""
    return validators.url(url) is True

def calculate_expiry_date(days: int) -> datetime:
    """Calculate expiry date from current time"""
    if days is None or days <= 0:
        return None
    return datetime.utcnow() + timedelta(days=days)

def anonymize_ip(ip: str) -> str:
    """
    Anonymize an IP address by hashing the last octet (IPv4) or the last 80 bits (IPv6)
    """
    if not ip or ip == "unknown":
        return "unknown"
        
    try:
        ip_obj = ipaddress.ip_address(ip)
        
        if isinstance(ip_obj, ipaddress.IPv4Address):
            octets = str(ip_obj).split('.')
            return f"{octets[0]}.{octets[1]}.{octets[2]}.*"
        else:
            hex_str = ip_obj.exploded
            return f"{hex_str[:19]}:****:****:****:****"
    except Exception:
        return "invalid-ip"

def create_url_mapping(db, original_url, alias=None, expires_in_days=None):
    """Helper function to create a URL mapping or return existing one"""
    if alias:
        if not alias.isalnum():
            return None, "Alias can only contain alphanumeric characters"
            
        existing_url = db.query(models.URLMapping).filter(
            models.URLMapping.short_code == alias
        ).first()
        
        if existing_url:
            return None, "Custom alias already in use"
            
        short_code = alias
    else:
        existing_url = db.query(models.URLMapping).filter(
            models.URLMapping.original_url == original_url,
            (models.URLMapping.expires_at.is_(None) | (models.URLMapping.expires_at > datetime.utcnow()))
        ).first()
        
        if existing_url:
            return existing_url, None
            
        short_code = generate_short_code(original_url)
        
        while db.query(models.URLMapping).filter(
            models.URLMapping.short_code == short_code
        ).first():
            short_code = generate_random_code()
    
    expires_at = None
    if expires_in_days:
        expires_at = calculate_expiry_date(expires_in_days)
    
    url_mapping = models.URLMapping(
        original_url=original_url,
        short_code=short_code,
        expires_at=expires_at
    )
    
    db.add(url_mapping)
    db.commit()
    db.refresh(url_mapping)
    
    return url_mapping, None