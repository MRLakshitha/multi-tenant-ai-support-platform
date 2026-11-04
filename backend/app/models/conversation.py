from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(String(64), nullable=False, index=True)
    customer_name = Column(String(128), default="Customer")
    
    current_level = Column(String(16), default="L1")  # L1, L2, L3
    status = Column(String(32), default="ACTIVE")      # ACTIVE, RESOLVED, CLOSED
    resolution_level = Column(String(16), nullable=True)  # L1, L2, L3, or None
    
    selected_category_id = Column(String(64), nullable=True)
    context_order_id = Column(String(64), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    closed_at = Column(DateTime, nullable=True)

    tenant = relationship("Tenant", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")
    state = relationship("ConversationState", back_populates="conversation", uselist=False, cascade="all, delete-orphan")
    ticket = relationship("SupportTicket", back_populates="conversation", uselist=False)

class Message(Base):
    __tablename__ = "messages"

    id = Column(String(64), primary_key=True, index=True)
    conversation_id = Column(String(64), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    
    # Senders: "USER", "BOT_L1", "BOT_L2", "AGENT_L3", "SYSTEM"
    sender_role = Column(String(32), nullable=False)
    sender_name = Column(String(128), default="Assistant")
    content = Column(Text, nullable=False)
    
    # Clickable options / pills / action metadata
    options = Column(JSON, nullable=True)        # Predefined options (e.g. L1 categories or Yes/No)
    metadata_json = Column(JSON, default=dict)   # Action triggers, order info, citations
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")

class ConversationState(Base):
    __tablename__ = "conversation_states"

    id = Column(String(64), primary_key=True, index=True)
    conversation_id = Column(String(64), ForeignKey("conversations.id", ondelete="CASCADE"), unique=True, nullable=False)
    tenant_id = Column(String(64), nullable=False, index=True)
    
    extracted_entities = Column(JSON, default=dict)   # {"order_id": "ORD-123", "item": "shampoo"}
    dialogue_turn_count = Column(Integer, default=0)
    last_intent = Column(String(64), nullable=True)
    rag_retrieval_history = Column(JSON, default=list)
    state_payload = Column(JSON, default=dict)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="state")
