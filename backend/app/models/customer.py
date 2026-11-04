from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from app.core.database import Base

class CustomerProfile(Base):
    __tablename__ = "customer_profiles"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    external_customer_id = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    email = Column(String(128), nullable=True)
    phone = Column(String(32), nullable=True)
    loyalty_tier = Column(String(32), default="STANDARD")  # VIP, GOLD, STANDARD
    preferences = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
