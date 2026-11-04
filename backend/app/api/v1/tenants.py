import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.api.deps import get_db, require_roles, get_current_user
from app.models.tenant import Tenant, TenantConfig
from app.models.user import User, UserRole

router = APIRouter()

class TenantConfigSchema(BaseModel):
    primary_color: str
    accent_color: str
    logo_emoji: str
    bot_name: str
    welcome_message: str
    support_email: str
    support_phone: str
    auto_refund_limit: float
    max_l2_turns_before_escalate: int

class TenantResponse(BaseModel):
    id: str
    code: str
    name: str
    industry: str
    domain: Optional[str]
    is_active: bool
    config: Optional[TenantConfigSchema]

class CreateTenantRequest(BaseModel):
    id: str
    code: str
    name: str
    industry: str
    domain: Optional[str] = None
    primary_color: str = "#4F46E5"
    accent_color: str = "#EC4899"
    logo_emoji: str = "🏢"
    bot_name: str = "Assistant"
    welcome_message: str = "Hello! Welcome to Support. How can I help you today?"
    support_email: str = "support@example.com"
    support_phone: str = "+1-800-555-0199"
    auto_refund_limit: float = 25.0

class UpdateTenantConfigRequest(BaseModel):
    primary_color: Optional[str] = None
    accent_color: Optional[str] = None
    logo_emoji: Optional[str] = None
    bot_name: Optional[str] = None
    welcome_message: Optional[str] = None
    support_email: Optional[str] = None
    support_phone: Optional[str] = None
    auto_refund_limit: Optional[float] = None
    max_l2_turns_before_escalate: Optional[int] = None

@router.get("", response_model=List[TenantResponse])
def list_tenants(db: Session = Depends(get_db)):
    """Public/Admin: Lists all available active tenants."""
    tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
    out = []
    for t in tenants:
        cfg = t.config
        cfg_dict = None
        if cfg:
            cfg_dict = {
                "primary_color": cfg.primary_color,
                "accent_color": cfg.accent_color,
                "logo_emoji": cfg.logo_emoji,
                "bot_name": cfg.bot_name,
                "welcome_message": cfg.welcome_message,
                "support_email": cfg.support_email,
                "support_phone": cfg.support_phone,
                "auto_refund_limit": cfg.auto_refund_limit,
                "max_l2_turns_before_escalate": cfg.max_l2_turns_before_escalate
            }
        out.append({
            "id": t.id,
            "code": t.code,
            "name": t.name,
            "industry": t.industry,
            "domain": t.domain,
            "is_active": t.is_active,
            "config": cfg_dict
        })
    return out

@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(tenant_id: str, db: Session = Depends(get_db)):
    t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    cfg = t.config
    cfg_dict = None
    if cfg:
        cfg_dict = {
            "primary_color": cfg.primary_color,
            "accent_color": cfg.accent_color,
            "logo_emoji": cfg.logo_emoji,
            "bot_name": cfg.bot_name,
            "welcome_message": cfg.welcome_message,
            "support_email": cfg.support_email,
            "support_phone": cfg.support_phone,
            "auto_refund_limit": cfg.auto_refund_limit,
            "max_l2_turns_before_escalate": cfg.max_l2_turns_before_escalate
        }
    return {
        "id": t.id,
        "code": t.code,
        "name": t.name,
        "industry": t.industry,
        "domain": t.domain,
        "is_active": t.is_active,
        "config": cfg_dict
    }

@router.post("", dependencies=[Depends(require_roles([UserRole.SUPER_ADMIN.value]))])
def create_tenant(req: CreateTenantRequest, db: Session = Depends(get_db)):
    """Admin only: Dynamically provisions a new customer tenant without code changes."""
    existing = db.query(Tenant).filter((Tenant.id == req.id) | (Tenant.code == req.code)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tenant with this ID or Code already exists")

    tenant = Tenant(
        id=req.id.strip().lower(),
        code=req.code.strip().upper(),
        name=req.name,
        industry=req.industry,
        domain=req.domain,
        is_active=True
    )
    db.add(tenant)
    db.flush()

    config = TenantConfig(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        primary_color=req.primary_color,
        accent_color=req.accent_color,
        logo_emoji=req.logo_emoji,
        bot_name=req.bot_name,
        welcome_message=req.welcome_message,
        support_email=req.support_email,
        support_phone=req.support_phone,
        auto_refund_limit=req.auto_refund_limit
    )
    db.add(config)
    db.commit()
    return {"status": "SUCCESS", "tenant_id": tenant.id, "name": tenant.name}

@router.put("/{tenant_id}/config")
def update_tenant_config(
    tenant_id: str,
    req: UpdateTenantConfigRequest,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN.value, UserRole.TENANT_ADMIN.value])),
    db: Session = Depends(get_db)
):
    """Updates tenant-specific branding and business policies."""
    # Enforce tenant isolation for TENANT_ADMIN
    if current_user.role == UserRole.TENANT_ADMIN.value and current_user.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Cannot alter another tenant's configuration")

    config = db.query(TenantConfig).filter(TenantConfig.tenant_id == tenant_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Tenant config not found")

    for field, val in req.dict(exclude_unset=True).items():
        if val is not None:
            setattr(config, field, val)

    db.commit()
    return {"status": "UPDATED", "tenant_id": tenant_id}
