from typing import Optional, List, Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_verified_tenant, require_roles, get_current_user
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.services.l3_service import L3SupportService

router = APIRouter()

class AgentMessageRequest(BaseModel):
    content: str

class UpdateStatusRequest(BaseModel):
    status: Literal["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"]
    resolution_notes: Optional[str] = None

class AddNoteRequest(BaseModel):
    note_text: str

class CallbackRequestSchema(BaseModel):
    conversation_id: str
    customer_name: str
    customer_phone: str
    preferred_time_slot: str = "ASAP"
    notes: Optional[str] = ""

class CallbackOutcomeRequest(BaseModel):
    status: str = "COMPLETED"
    duration_seconds: int = 180
    outcome_notes: str

@router.get("")
def list_tickets(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    tenant: Tenant = Depends(get_verified_tenant),
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN.value, UserRole.TENANT_ADMIN.value, UserRole.SUPPORT_AGENT.value])),
    db: Session = Depends(get_db)
):
    """Lists support tickets for the current tenant queue."""
    agent_id = None
    if current_user.role == UserRole.SUPPORT_AGENT.value and current_user.agent_profile:
        # Agents can see tenant tickets, optionally filtered
        pass
    tickets = L3SupportService.get_agent_tickets(
        db=db,
        tenant_id=tenant.id,
        agent_id=agent_id,
        status_filter=status,
        priority_filter=priority
    )
    return tickets

@router.get("/{ticket_id}")
def get_ticket(
    ticket_id: str,
    tenant: Tenant = Depends(get_verified_tenant),
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN.value, UserRole.TENANT_ADMIN.value, UserRole.SUPPORT_AGENT.value])),
    db: Session = Depends(get_db)
):
    """Retrieves full ticket context, conversation transcript, internal notes, and verified order details."""
    try:
        details = L3SupportService.get_ticket_details(db, tenant.id, ticket_id)
        return details
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{ticket_id}/message")
def send_agent_reply(
    ticket_id: str,
    req: AgentMessageRequest,
    tenant: Tenant = Depends(get_verified_tenant),
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN.value, UserRole.TENANT_ADMIN.value, UserRole.SUPPORT_AGENT.value])),
    db: Session = Depends(get_db)
):
    """Agent replies directly to customer within ticket conversation."""
    agent_id = current_user.agent_profile.id if current_user.agent_profile else current_user.id
    res = L3SupportService.send_agent_message(
        db=db,
        tenant_id=tenant.id,
        ticket_id=ticket_id,
        agent_id=agent_id,
        agent_name=current_user.full_name,
        content=req.content
    )
    return res

@router.post("/{ticket_id}/status")
def update_status(
    ticket_id: str,
    req: UpdateStatusRequest,
    tenant: Tenant = Depends(get_verified_tenant),
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN.value, UserRole.TENANT_ADMIN.value, UserRole.SUPPORT_AGENT.value])),
    db: Session = Depends(get_db)
):
    """Updates ticket lifecycle status (OPEN, IN_PROGRESS, RESOLVED, CLOSED)."""
    res = L3SupportService.update_ticket_status(
        db=db,
        tenant_id=tenant.id,
        ticket_id=ticket_id,
        new_status=req.status,
        resolution_notes=req.resolution_notes
    )
    return res

@router.post("/{ticket_id}/notes")
def add_internal_note(
    ticket_id: str,
    req: AddNoteRequest,
    tenant: Tenant = Depends(get_verified_tenant),
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN.value, UserRole.TENANT_ADMIN.value, UserRole.SUPPORT_AGENT.value])),
    db: Session = Depends(get_db)
):
    """Adds internal agent-only note for team collaboration."""
    agent_id = current_user.agent_profile.id if current_user.agent_profile else current_user.id
    res = L3SupportService.add_internal_note(
        db=db,
        tenant_id=tenant.id,
        ticket_id=ticket_id,
        agent_id=agent_id,
        agent_name=current_user.full_name,
        note_text=req.note_text
    )
    return res

# ----------------- Callback Integration -----------------

@router.post("/callback/request")
def request_callback(
    req: CallbackRequestSchema,
    tenant: Tenant = Depends(get_verified_tenant),
    db: Session = Depends(get_db)
):
    """Customer submits request for phone callback."""
    try:
        res = L3SupportService.request_callback(
            db=db,
            tenant_id=tenant.id,
            conversation_id=req.conversation_id,
            customer_phone=req.customer_phone,
            customer_name=req.customer_name,
            preferred_time_slot=req.preferred_time_slot,
            notes=req.notes
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/callback/list")
def list_callbacks(
    tenant: Tenant = Depends(get_verified_tenant),
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN.value, UserRole.TENANT_ADMIN.value, UserRole.SUPPORT_AGENT.value])),
    db: Session = Depends(get_db)
):
    """Agent views scheduled callback request queue."""
    return L3SupportService.get_pending_callbacks(db, tenant.id)

@router.post("/callback/{call_id}/outcome")
def complete_callback(
    call_id: str,
    req: CallbackOutcomeRequest,
    tenant: Tenant = Depends(get_verified_tenant),
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN.value, UserRole.TENANT_ADMIN.value, UserRole.SUPPORT_AGENT.value])),
    db: Session = Depends(get_db)
):
    """Agent logs call duration and outcome notes."""
    agent_id = current_user.agent_profile.id if current_user.agent_profile else current_user.id
    res = L3SupportService.update_callback_outcome(
        db=db,
        tenant_id=tenant.id,
        call_id=call_id,
        agent_id=agent_id,
        status=req.status,
        duration_seconds=req.duration_seconds,
        outcome_notes=req.outcome_notes
    )
    return res
