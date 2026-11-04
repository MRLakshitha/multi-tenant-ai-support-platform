from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text
from app.core.database import Base

class CallRequest(Base):
    __tablename__ = "call_requests"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(String(64), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(String(64), nullable=False, index=True)
    customer_name = Column(String(128), nullable=False)
    customer_phone = Column(String(32), nullable=False)
    
    preferred_time_slot = Column(String(64), default="ASAP")  # ASAP, Within 15 Mins, Evening
    issue_summary = Column(Text, nullable=False)
    
    # Statuses: PENDING, SCHEDULED, IN_PROGRESS, COMPLETED, CANCELLED
    status = Column(String(32), default="PENDING", index=True)
    assigned_agent_id = Column(String(64), ForeignKey("support_agents.id", ondelete="SET NULL"), nullable=True)
    
    call_duration_seconds = Column(Integer, default=0)
    call_outcome_notes = Column(Text, nullable=True)
    telephony_provider = Column(String(32), default="MOCK_TELEPHONY")
    telephony_call_sid = Column(String(64), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
