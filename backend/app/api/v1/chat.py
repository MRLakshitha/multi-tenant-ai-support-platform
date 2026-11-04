from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_verified_tenant
from app.models.tenant import Tenant
from app.models.conversation import Conversation, Message
from app.services.l1_engine import L1Engine
from app.services.l2_engine import L2ConversationalEngine
from app.services.analytics_service import AnalyticsService

router = APIRouter()

def verify_conversation_tenant(
    db: Session,
    conversation_id: str,
    tenant_id: str
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.tenant_id == tenant_id
    ).first()

    if not conv:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found"
        )

    return conv
class StartChatRequest(BaseModel):
    customer_id: Optional[str] = "cust-user-guest"
    customer_name: Optional[str] = "Guest Customer"

class OptionSelectRequest(BaseModel):
    conversation_id: str
    category_id: str

class OrderInputRequest(BaseModel):
    conversation_id: str
    input_text: str

class ResolutionConfirmRequest(BaseModel):
    conversation_id: str
    resolved: bool

class SendMessageRequest(BaseModel):
    conversation_id: str
    message: str

class FeedbackRequest(BaseModel):
    conversation_id: str
    customer_id: str
    rating: int
    feedback_text: Optional[str] = ""

@router.post("/start")
def start_chat(
    req: StartChatRequest,
    tenant: Tenant = Depends(get_verified_tenant),
    db: Session = Depends(get_db)
):
    """
    Initializes L1 automated support.
    Returns tenant branding, welcome message, and predefined clickable issue categories.
    """
    res = L1Engine.start_conversation(
        db=db,
        tenant_id=tenant.id,
        customer_id=req.customer_id,
        customer_name=req.customer_name
    )
    return res

@router.post("/select-option")
def select_option(
    req: OptionSelectRequest,
    tenant: Tenant = Depends(get_verified_tenant),
    db: Session = Depends(get_db)
):
    """Handles selection of predefined clickable categories/subcategories."""
    try:
        verify_conversation_tenant(db, req.conversation_id, tenant.id)

        res = L1Engine.handle_option_selection(
            db=db,
            conversation_id=req.conversation_id,
            category_id=req.category_id
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/order-input")
def order_input(
    req: OrderInputRequest,
    tenant: Tenant = Depends(get_verified_tenant),
    db: Session = Depends(get_db)
):
    """Handles submission of Order ID or Reference ID for deterministic verification."""
    try:
        verify_conversation_tenant(db, req.conversation_id, tenant.id)

        res = L1Engine.handle_order_input(
            db=db,
            conversation_id=req.conversation_id,
            input_text=req.input_text
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/confirm-resolution")
def confirm_resolution(
    req: ResolutionConfirmRequest,
    tenant: Tenant = Depends(get_verified_tenant),
    db: Session = Depends(get_db)
):
    """
    Handles resolution confirmation.
    If resolved -> Closes session & prompts CSAT.
    If unresolved -> Escalate to L2 Conversational AI.
    """
    try:
        verify_conversation_tenant(db, req.conversation_id, tenant.id)

        res = L1Engine.handle_resolution_confirmation(
            db=db,
            conversation_id=req.conversation_id,
            resolved=req.resolved
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/message")
async def send_conversational_message(
    req: SendMessageRequest,
    tenant: Tenant = Depends(get_verified_tenant),
    db: Session = Depends(get_db)
):
    """
    L2 Conversational AI input.
    Processes natural-language queries, runs intent classification,
    entity extraction, tenant-isolated RAG, and escalation decisions.
    """
    try:
        verify_conversation_tenant(db, req.conversation_id, tenant.id)

        res = await L2ConversationalEngine.process_message(
            db=db,
            conversation_id=req.conversation_id,
            user_text=req.message
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/feedback")
def submit_feedback(
    req: FeedbackRequest,
    tenant: Tenant = Depends(get_verified_tenant),
    db: Session = Depends(get_db)
):
    """Submits CSAT star rating and optional comments."""
    verify_conversation_tenant(db, req.conversation_id, tenant.id)

    res = AnalyticsService.record_feedback(
        db=db,
        tenant_id=tenant.id,
        conversation_id=req.conversation_id,
        customer_id=req.customer_id,
        rating=req.rating,
        feedback_text=req.feedback_text
    )
    return res

@router.get("/{conversation_id}/history")
def get_chat_history(
    conversation_id: str,
    tenant: Tenant = Depends(get_verified_tenant),
    db: Session = Depends(get_db)
):
    """Retrieves full conversation history across L1, L2, and L3 levels."""
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.tenant_id == tenant.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.asc()).all()

    return {
        "conversation_id": conv.id,
        "current_level": conv.current_level,
        "status": conv.status,
        "resolution_level": conv.resolution_level,
        "messages": [
            {
                "id": m.id,
                "role": m.sender_role,
                "sender": m.sender_name,
                "content": m.content,
                "options": m.options,
                "metadata": m.metadata_json,
                "timestamp": m.created_at.isoformat()
            }
            for m in messages
        ]
    }
