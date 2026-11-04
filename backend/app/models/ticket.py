from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base

class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(String(64), primary_key=True, index=True)  # e.g. "TICK-FRESH-001"
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(String(64), ForeignKey("conversations.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    customer_id = Column(String(64), nullable=False, index=True)
    customer_name = Column(String(128), default="Customer")
    customer_phone = Column(String(32), nullable=True)
    customer_email = Column(String(128), nullable=True)
    
    issue_category = Column(String(128), nullable=False)
    issue_description = Column(Text, nullable=False)
    ai_summary = Column(Text, nullable=True)
    
    # Priority: "URGENT", "HIGH", "MEDIUM", "LOW"
    priority = Column(String(16), default="MEDIUM", index=True)
    # Statuses: "OPEN", "PENDING", "ASSIGNED", "IN_PROGRESS", "WAITING_FOR_CUSTOMER", "RESOLVED", "CLOSED"
    status = Column(String(32), default="OPEN", index=True)
    escalation_reason = Column(String(256), nullable=False)
    
    assigned_agent_id = Column(String(64), ForeignKey("support_agents.id", ondelete="SET NULL"), nullable=True, index=True)
    resolution_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    tenant = relationship("Tenant", back_populates="tickets")
    conversation = relationship("Conversation", back_populates="ticket")
    assigned_agent = relationship("SupportAgent", back_populates="assigned_tickets")
    notes = relationship("TicketNote", back_populates="ticket", cascade="all, delete-orphan")
    assignments = relationship("TicketAssignment", back_populates="ticket", cascade="all, delete-orphan")

class TicketAssignment(Base):
    __tablename__ = "ticket_assignments"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    ticket_id = Column(String(64), ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(64), ForeignKey("support_agents.id", ondelete="CASCADE"), nullable=False)
    assigned_by = Column(String(64), nullable=False)  # User ID or "AUTO_SYSTEM"
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    ticket = relationship("SupportTicket", back_populates="assignments")

class TicketNote(Base):
    __tablename__ = "ticket_notes"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    ticket_id = Column(String(64), ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(64), nullable=False)
    agent_name = Column(String(128), nullable=False)
    note_text = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=True)  # True = agent only; False = customer-visible note
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    ticket = relationship("SupportTicket", back_populates="notes")

class EscalationRecord(Base):
    __tablename__ = "escalation_records"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(String(64), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    from_level = Column(String(16), nullable=False)  # L1 or L2
    to_level = Column(String(16), nullable=False)    # L2 or L3
    reason = Column(String(256), nullable=False)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
