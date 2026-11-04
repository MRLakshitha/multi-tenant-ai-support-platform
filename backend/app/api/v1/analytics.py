from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_verified_tenant, require_roles
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.services.analytics_service import AnalyticsService

router = APIRouter()

@router.get("/dashboard")
def get_analytics_dashboard(
    tenant_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN.value, UserRole.TENANT_ADMIN.value, UserRole.SUPPORT_AGENT.value])),
    db: Session = Depends(get_db)
):
    """
    Computes true live analytics from stored conversation outcomes and tickets.
    Tenant admins are restricted to their own tenant; Super Admins can filter by tenant or view global stats.
    """
    target_tenant = tenant_id
    if current_user.role != UserRole.SUPER_ADMIN.value:
        target_tenant = current_user.tenant_id

    metrics = AnalyticsService.get_dashboard_metrics(
        db=db,
        tenant_id=target_tenant,
        days=days
    )
    return metrics
