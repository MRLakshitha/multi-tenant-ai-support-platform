from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Text, JSON, Float
from sqlalchemy.orm import relationship
from app.core.database import Base

class L1Workflow(Base):
    __tablename__ = "l1_workflows"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(String(64), ForeignKey("issue_categories.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    
    # Workflow Logic
    required_fields = Column(JSON, default=list)  # ["order_id", "item_id", "reason"]
    condition_rules = Column(JSON, default=dict)   # e.g., {"order_status_in": ["DELIVERED", "TRANSIT"], "delivered_under_hours": 2}
    automated_action_type = Column(String(64), nullable=True)  # REFUND, REPLACEMENT, DRIVER_RETRY, CANCEL_ORDER
    max_auto_amount = Column(Float, default=25.0)
    
    success_response_template = Column(Text, nullable=False)
    fallback_response_template = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    category = relationship("IssueCategory", back_populates="workflows")

class L1Action(Base):
    __tablename__ = "l1_actions"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(String(64), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id = Column(String(64), ForeignKey("l1_workflows.id", ondelete="SET NULL"), nullable=True)
    action_type = Column(String(64), nullable=False)  # REFUND, REPLACEMENT, CANCEL, STATUS_CHECK
    parameters = Column(JSON, default=dict)
    execution_status = Column(String(32), default="SUCCESS")  # SUCCESS, FAILED, REJECTED
    result_summary = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
