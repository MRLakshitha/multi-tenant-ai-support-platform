from typing import Optional, List
from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from app.core.config import settings
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.models.tenant import Tenant

# Synchronous DB session helper for standard FastAPI dependency injection
sync_engine = create_engine(settings.SYNC_DATABASE_URL, echo=False)

def get_db():
    db = Session(bind=sync_engine)
    try:
        yield db
    finally:
        db.close()

security_scheme = HTTPBearer(auto_error=False)

def get_tenant_header(x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID")) -> Optional[str]:
    return x_tenant_id

def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    if not auth:
        return None
    token = auth.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token"
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user

def require_auth(current_user: Optional[User] = Depends(get_current_user)) -> User:
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for this resource"
        )
    return current_user

def require_roles(allowed_roles: List[str]):
    def role_checker(user: User = Depends(require_auth)) -> User:
        if user.role == UserRole.SUPER_ADMIN.value:
            return user  # Super Admin has access to everything
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Requires one of roles {allowed_roles}"
            )
        return user
    return role_checker

def get_verified_tenant(
    x_tenant_id: Optional[str] = Depends(get_tenant_header),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Tenant:
    """
    Enforces strict tenant isolation:
    1. If user is authenticated and not SUPER_ADMIN, tenant MUST match user's tenant_id.
    2. If user is SUPER_ADMIN, they can operate on behalf of x_tenant_id.
    3. If public/anonymous (e.g. chatbot customer), x_tenant_id must be a valid, active tenant.
    """
    target_tenant_id = None
    
    if current_user:
        if current_user.role != UserRole.SUPER_ADMIN.value:
            target_tenant_id = current_user.tenant_id
            if x_tenant_id and x_tenant_id != target_tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cross-tenant access violation: Cannot access another tenant's resources"
                )
        else:
            target_tenant_id = x_tenant_id or "cust-a-freshcart"
    else:
        target_tenant_id = x_tenant_id

    if not target_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant ID is required (provide X-Tenant-ID header)"
        )

    tenant = db.query(Tenant).filter(Tenant.id == target_tenant_id, Tenant.is_active == True).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{target_tenant_id}' not found or inactive"
        )
    return tenant
