from sqlalchemy import Column, Integer, String, DateTime, func, Index, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class URLMapping(Base):
    __tablename__ = "url_mappings"

    id = Column(Integer, primary_key=True, index=True)
    original_url = Column(String, nullable=False)
    short_code = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=True)
    clicks = Column(Integer, default=0)
    
    statistics = relationship("URLStatistics", back_populates="url_mapping", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_short_code", short_code),
        Index("idx_original_url", original_url),
    )

class URLStatistics(Base):
    __tablename__ = "url_statistics"

    id = Column(Integer, primary_key=True, index=True)
    url_mapping_id = Column(Integer, ForeignKey("url_mappings.id", ondelete="CASCADE"), nullable=False)
    clicked_at = Column(DateTime, default=func.now())
    referrer = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    
    url_mapping = relationship("URLMapping", back_populates="statistics")