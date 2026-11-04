from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Float, Integer, JSON, Text
from sqlalchemy.orm import relationship
from app.core.database import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(64), primary_key=True, index=True)  # e.g., "cust-a-freshcart"
    code = Column(String(32), unique=True, index=True, nullable=False)
    name = Column(String(128), nullable=False)
    industry = Column(String(64), nullable=False)
    domain = Column(String(128), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    config = relationship("TenantConfig", back_populates="tenant", uselist=False, cascade="all, delete-orphan")
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    categories = relationship("IssueCategory", back_populates="tenant", cascade="all, delete-orphan")
    knowledge_docs = relationship("KnowledgeDocument", back_populates="tenant", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="tenant", cascade="all, delete-orphan")
    tickets = relationship("SupportTicket", back_populates="tenant", cascade="all, delete-orphan")
    agents = relationship("SupportAgent", back_populates="tenant", cascade="all, delete-orphan")

class TenantConfig(Base):
    __tablename__ = "tenant_configs"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    
    # Branding
    primary_color = Column(String(32), default="#4F46E5")
    accent_color = Column(String(32), default="#EC4899")
    logo_emoji = Column(String(16), default="🛒")
    bot_name = Column(String(64), default="Support Assistant")
    welcome_message = Column(Text, default="Hello! Welcome to Support. How can I help you today?")
    
    # Contact & SLA
    support_email = Column(String(128), default="support@example.com")
    support_phone = Column(String(32), default="+1-800-555-0199")
    business_hours_start = Column(String(8), default="08:00")
    business_hours_end = Column(String(8), default="23:00")
    timezone = Column(String(64), default="UTC")
    
    # Escalation & AI Rules
    auto_refund_limit = Column(Float, default=25.0)  # Max instant refund dollar/rupee limit
    l2_confidence_threshold = Column(Float, default=0.7)
    max_l2_turns_before_escalate = Column(Integer, default=5)
    enable_callback = Column(Boolean, default=True)
    custom_policies = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant", back_populates="config")
