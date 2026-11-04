from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, JSON
from app.core.database import Base

class FeedbackRating(Base):
    __tablename__ = "feedback_ratings"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(String(64), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(String(64), nullable=False)
    rating = Column(Integer, nullable=False)  # 1 to 5 stars
    feedback_text = Column(Text, nullable=True)
    resolved_by_level = Column(String(16), nullable=False)  # L1, L2, or L3
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=True, index=True)  # Nullable for superadmin actions
    user_id = Column(String(64), nullable=True, index=True)
    action = Column(String(64), nullable=False)  # CREATE_TENANT, ESCALATE_TICKET, REASSIGN_AGENT, ISSUE_REFUND
    resource_type = Column(String(64), nullable=False)  # TICKET, CONVERSATION, TENANT, KNOWLEDGE_BASE
    resource_id = Column(String(64), nullable=True)
    details = Column(JSON, default=dict)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
