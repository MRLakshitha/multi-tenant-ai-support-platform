from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship, backref
from app.core.database import Base

class IssueCategory(Base):
    __tablename__ = "issue_categories"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id = Column(String(64), ForeignKey("issue_categories.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(32), default="tag")
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    requires_order = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant", back_populates="categories")
    parent = relationship("IssueCategory", remote_side=[id], backref=backref("subcategories", cascade="all, delete-orphan"))
    workflows = relationship("L1Workflow", back_populates="category", cascade="all, delete-orphan")
