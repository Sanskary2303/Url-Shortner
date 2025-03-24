import logging
import json
import os
from datetime import datetime

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "json") 

logger = logging.getLogger("url_shortener")
logger.setLevel(getattr(logging, LOG_LEVEL))

handler = logging.StreamHandler()
handler.setLevel(getattr(logging, LOG_LEVEL))

if LOG_FORMAT.lower() == "json":
    class JsonFormatter(logging.Formatter):
        def format(self, record):
            log_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": record.levelname,
                "message": record.getMessage(),
            }
            
            if record.exc_info:
                log_data["exception"] = self.formatException(record.exc_info)
                
            for key, value in record.__dict__.items():
                if key not in ["args", "asctime", "created", "exc_info", 
                               "exc_text", "filename", "funcName", "id", 
                               "levelname", "levelno", "lineno", "module", 
                               "msecs", "message", "msg", "name", "pathname", 
                               "process", "processName", "relativeCreated", 
                               "stack_info", "thread", "threadName"]:
                    log_data[key] = value
                    
            return json.dumps(log_data)
    
    formatter = JsonFormatter()
else:
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

handler.setFormatter(formatter)
logger.addHandler(handler)

def log_request(request, route):
    """Log incoming request"""
    logger.info(
        "Request received", 
        extra={
            "route": route, 
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host if request.client else "unknown"
        }
    )

def log_url_created(short_code, original_url):
    """Log URL creation"""
    logger.info(
        "URL shortened", 
        extra={
            "short_code": short_code,
            "original_url": original_url
        }
    )

def log_url_accessed(short_code):
    """Log URL access"""
    logger.info(
        "URL accessed", 
        extra={
            "short_code": short_code
        }
    )

def log_error(message, error=None, **kwargs):
    """Log error"""
    extra = kwargs
    if error:
        extra["error_type"] = type(error).__name__
        extra["error_message"] = str(error)
    
    logger.error(message, extra=extra)