import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.category import IssueCategory
from app.models.conversation import Conversation, Message
from app.models.ticket import SupportTicket, TicketAssignment, TicketNote, EscalationRecord
from app.models.user import SupportAgent
from app.models.callback import CallRequest
from app.models.audit import AuditLog
from app.services.mock_external_api import MockExternalAPIService

class L3SupportService:
    """
    L3 Human Support, Ticketing, Live Agent Workflow, and Telephony/Callback Management.
    """
    @classmethod
    def create_escalation_ticket(
        cls,
        db: Session,
        conversation_id: str,
        tenant_id: str,
        escalation_reason: str,
        priority: str = "MEDIUM",
        customer_latest_message: str = ""
    ) -> Dict[str, Any]:
        conv = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant_id
        ).first()

        if not conv:
            raise ValueError("Conversation not found")
        tenant_id = conv.tenant_id

        # Prevent duplicate tickets for same conversation
        existing_ticket = db.query(SupportTicket).filter(
            SupportTicket.conversation_id == conversation_id,
            SupportTicket.tenant_id == tenant_id
        ).first()
        if existing_ticket:
            return {
                "ticket_id": existing_ticket.id,
                "status": existing_ticket.status,
                "assigned_agent_id": existing_ticket.assigned_agent_id,
                "already_exists": True
            }

        # Build AI Summary from conversation history
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at).all()

        chat_snippets = []
        for m in messages:
            chat_snippets.append(f"{m.sender_role}: {m.content[:120]}")
        conversation_context = "\n".join(chat_snippets)

        # Generate intelligent summary
        entities = conv.state.extracted_entities if conv.state else {}
        order_info = f" Order: {conv.context_order_id}." if conv.context_order_id else ""
        item_info = f" Item: {entities.get('item_name')}." if entities.get('item_name') else ""
        ai_summary = (
            f"Escalated from {conv.current_level} due to: {escalation_reason}.{order_info}{item_info} "
            f"Customer expressed: '{customer_latest_message[:150]}'."
        )

        ticket_code = f"TICK-{conv.tenant.code}-{uuid.uuid4().hex[:6].upper()}"

        # Auto-assign to available agent with lowest workload
        available_agent = db.query(SupportAgent).filter(
            SupportAgent.tenant_id == tenant_id,
            SupportAgent.is_online == True
        ).order_by(SupportAgent.active_tickets_count.asc()).first()

        assigned_agent_id = available_agent.id if available_agent else None
        initial_status = "ASSIGNED" if available_agent else "OPEN"

        # Retrieve verified customer contact details
        customer_contact = MockExternalAPIService.get_customer_contact(
            tenant_id=tenant_id,
            customer_id=conv.customer_id
        ) or {}

        # Retrieve the readable issue category name
        selected_category = None

        if conv.selected_category_id:
            selected_category = db.query(IssueCategory).filter(
                IssueCategory.id == conv.selected_category_id,
                IssueCategory.tenant_id == tenant_id
            ).first()

        issue_category_name = (
            selected_category.name
            if selected_category
            else "General Support"
        )

        ticket = SupportTicket(
            id=ticket_code,
            tenant_id=tenant_id,
            conversation_id=conv.id,
            customer_id=conv.customer_id,
            customer_name=conv.customer_name,
            customer_phone=customer_contact.get("customer_phone"),
            customer_email=customer_contact.get("customer_email"),
            issue_category=issue_category_name,
            issue_description=customer_latest_message or "Customer requested human escalation",
            ai_summary=ai_summary,
            priority=priority,
            status=initial_status,
            escalation_reason=escalation_reason,
            assigned_agent_id=assigned_agent_id,
            created_at=datetime.utcnow()
        )
        db.add(ticket)

        # Update conversation status
        conv.current_level = "L3"
        conv.status = "ESCALATED"

        # Record Escalation
        esc_record = EscalationRecord(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            conversation_id=conv.id,
            from_level="L2",
            to_level="L3",
            reason=escalation_reason,
            details={"priority": priority, "ticket_id": ticket_code},
            created_at=datetime.utcnow()
        )
        db.add(esc_record)

        if available_agent:
            available_agent.active_tickets_count = (available_agent.active_tickets_count or 0) + 1
            assignment = TicketAssignment(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                ticket_id=ticket.id,
                agent_id=available_agent.id,
                assigned_by="AUTO_DISPATCHER",
                assigned_at=datetime.utcnow()
            )
            db.add(assignment)

        # Log audit
        audit = AuditLog(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            action="CREATE_ESCALATION_TICKET",
            resource_type="TICKET",
            resource_id=ticket.id,
            details={"priority": priority, "reason": escalation_reason}
        )
        db.add(audit)
        db.commit()

        return {
            "ticket_id": ticket.id,
            "status": ticket.status,
            "priority": ticket.priority,
            "assigned_agent": available_agent.display_name if available_agent else "Unassigned",
            "ai_summary": ai_summary,
            "already_exists": False
        }

    @staticmethod
    def get_agent_tickets(
        db: Session,
        tenant_id: str,
        agent_id: Optional[str] = None,
        status_filter: Optional[str] = None,
        priority_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = db.query(SupportTicket).filter(SupportTicket.tenant_id == tenant_id)
        if agent_id:
            query = query.filter(SupportTicket.assigned_agent_id == agent_id)
        if status_filter:
            query = query.filter(SupportTicket.status == status_filter)
        if priority_filter:
            query = query.filter(SupportTicket.priority == priority_filter)

        tickets = query.order_by(SupportTicket.created_at.desc()).all()
        result = []
        for t in tickets:
            result.append({
                "id": t.id,
                "tenant_id": t.tenant_id,
                "conversation_id": t.conversation_id,
                "customer_name": t.customer_name,
                "customer_phone": t.customer_phone,
                "issue_category": t.issue_category,
                "priority": t.priority,
                "status": t.status,
                "escalation_reason": t.escalation_reason,
                "ai_summary": t.ai_summary,
                "assigned_agent_id": t.assigned_agent_id,
                "assigned_agent_name": t.assigned_agent.display_name if t.assigned_agent else "Unassigned",
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat()
            })
        return result

    @staticmethod
    def get_ticket_details(db: Session, tenant_id: str, ticket_id: str) -> Dict[str, Any]:
        ticket = db.query(SupportTicket).filter(
            SupportTicket.id == ticket_id,
            SupportTicket.tenant_id == tenant_id
        ).first()
        if not ticket:
            raise ValueError("Ticket not found")

        # Fetch full conversation history
        messages = db.query(Message).filter(
            Message.conversation_id == ticket.conversation_id
        ).order_by(Message.created_at.asc()).all()

        message_history = [
            {
                "id": m.id,
                "role": m.sender_role,
                "sender": m.sender_name,
                "content": m.content,
                "timestamp": m.created_at.isoformat(),
                "options": m.options,
                "metadata": m.metadata_json
            }
            for m in messages
        ]

        # Fetch internal notes
        notes = db.query(TicketNote).filter(
            TicketNote.ticket_id == ticket.id
        ).order_by(TicketNote.created_at.asc()).all()

        notes_data = [
            {
                "id": n.id,
                "agent_name": n.agent_name,
                "note_text": n.note_text,
                "is_internal": n.is_internal,
                "timestamp": n.created_at.isoformat()
            }
            for n in notes
        ]

       
        # Verified Order Details if available
        order_details = None
        conv = ticket.conversation

        if conv and conv.context_order_id and conv.customer_id:
            order_details = MockExternalAPIService.get_order_details(
                tenant_id=tenant_id,
                order_id=conv.context_order_id,
                customer_id=conv.customer_id
            )

        return {
            "ticket": {
                "id": ticket.id,
                "tenant_id": ticket.tenant_id,
                "conversation_id": ticket.conversation_id,
                "customer_name": ticket.customer_name,
                "customer_phone": ticket.customer_phone,
                "customer_email": ticket.customer_email,
                "issue_category": ticket.issue_category,
                "priority": ticket.priority,
                "status": ticket.status,
                "ai_summary": ticket.ai_summary,
                "escalation_reason": ticket.escalation_reason,
                "assigned_agent_id": ticket.assigned_agent_id,
                "assigned_agent_name": ticket.assigned_agent.display_name if ticket.assigned_agent else "Unassigned",
                "created_at": ticket.created_at.isoformat(),
                "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None
            },
            "order_details": order_details,
            "messages": message_history,
            "notes": notes_data
        }

    @staticmethod
    def send_agent_message(
        db: Session,
        tenant_id: str,
        ticket_id: str,
        agent_id: str,
        agent_name: str,
        content: str
    ) -> Dict[str, Any]:
        ticket = db.query(SupportTicket).filter(
            SupportTicket.id == ticket_id,
            SupportTicket.tenant_id == tenant_id
        ).first()
        if not ticket:
            raise ValueError("Ticket not found")

        # Add message to conversation
        msg = Message(
            id=f"msg-{uuid.uuid4().hex[:12]}",
            conversation_id=ticket.conversation_id,
            tenant_id=tenant_id,
            sender_role="AGENT_L3",
            sender_name=agent_name,
            content=content,
            metadata_json={"agent_id": agent_id, "ticket_id": ticket_id}
        )
        db.add(msg)

        # Update status if in progress
        if ticket.status in ["OPEN", "PENDING", "ASSIGNED"]:
            ticket.status = "IN_PROGRESS"
        ticket.updated_at = datetime.utcnow()
        db.commit()

        return {
            "message_id": msg.id,
            "conversation_id": ticket.conversation_id,
            "sender_name": agent_name,
            "content": content,
            "ticket_status": ticket.status,
            "timestamp": msg.created_at.isoformat()
        }

    @staticmethod
    def update_ticket_status(
        db: Session,
        tenant_id: str,
        ticket_id: str,
        new_status: str,
        resolution_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        ticket = db.query(SupportTicket).filter(
            SupportTicket.id == ticket_id,
            SupportTicket.tenant_id == tenant_id
        ).first()
        if not ticket:
            raise ValueError("Ticket not found")

        ticket.status = new_status
        ticket.updated_at = datetime.utcnow()

        if new_status in ["RESOLVED", "CLOSED"]:
            ticket.resolved_at = datetime.utcnow()
            ticket.resolution_notes = resolution_notes
            if ticket.conversation:
                ticket.conversation.status = "RESOLVED"
                ticket.conversation.resolution_level = "L3"
                ticket.conversation.closed_at = datetime.utcnow()

        db.commit()
        return {"ticket_id": ticket_id, "status": new_status, "updated_at": ticket.updated_at.isoformat()}

    @staticmethod
    def add_internal_note(
        db: Session,
        tenant_id: str,
        ticket_id: str,
        agent_id: str,
        agent_name: str,
        note_text: str
    ) -> Dict[str, Any]:
        ticket = db.query(SupportTicket).filter(
            SupportTicket.id == ticket_id,
            SupportTicket.tenant_id == tenant_id
        ).first()
        if not ticket:
            raise ValueError("Ticket not found")

        note = TicketNote(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            ticket_id=ticket.id,
            agent_id=agent_id,
            agent_name=agent_name,
            note_text=note_text,
            is_internal=True,
            created_at=datetime.utcnow()
        )
        db.add(note)
        db.commit()
        return {
            "note_id": note.id,
            "agent_name": agent_name,
            "note_text": note_text,
            "timestamp": note.created_at.isoformat()
        }

    @staticmethod
    def request_callback(
        db: Session,
        tenant_id: str,
        conversation_id: str,
        customer_phone: str,
        customer_name: str,
        preferred_time_slot: str = "ASAP",
        notes: str = ""
    ) -> Dict[str, Any]:
        """Creates a scheduled callback request in the agent queue."""

        conv = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant_id
        ).first()

        if not conv:
            raise ValueError("Conversation not found")

        req = CallRequest(
            
            id=f"CALL-{uuid.uuid4().hex[:8].upper()}",
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            customer_id=f"cust-{customer_name.lower().replace(' ', '-')}",
            customer_name=customer_name,
            customer_phone=customer_phone,
            preferred_time_slot=preferred_time_slot,
            issue_summary=notes or "Customer requested phone callback for unresolved issue",
            status="PENDING",
            created_at=datetime.utcnow()
        )
        db.add(req)

        # Notify inside conversation
        sys_msg = Message(
            id=f"msg-{uuid.uuid4().hex[:12]}",
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            sender_role="SYSTEM",
            sender_name="Telephony Dispatcher",
            content=(
                f"📞 **Callback Request Confirmed!**\n"
                f"Request ID: `{req.id}`\n"
                f"Phone: `{customer_phone}`\n"
                f"Time Slot: **{preferred_time_slot}**\n"
                f"A customer service specialist will call you directly."
            ),
            metadata_json={"type": "CALLBACK_CONFIRMED", "call_id": req.id}
        )
        db.add(sys_msg)
        db.commit()

        return {
            "call_id": req.id,
            "status": req.status,
            "phone": req.customer_phone,
            "time_slot": req.preferred_time_slot,
            "created_at": req.created_at.isoformat()
        }

    @staticmethod
    def get_pending_callbacks(db: Session, tenant_id: str) -> List[Dict[str, Any]]:
        calls = db.query(CallRequest).filter(
            CallRequest.tenant_id == tenant_id
        ).order_by(CallRequest.created_at.desc()).all()

        return [
            {
                "id": c.id,
                "conversation_id": c.conversation_id,
                "customer_name": c.customer_name,
                "customer_phone": c.customer_phone,
                "preferred_time_slot": c.preferred_time_slot,
                "issue_summary": c.issue_summary,
                "status": c.status,
                "assigned_agent_id": c.assigned_agent_id,
                "call_outcome_notes": c.call_outcome_notes,
                "created_at": c.created_at.isoformat()
            }
            for c in calls
        ]

    @staticmethod
    def update_callback_outcome(
        db: Session,
        tenant_id: str,
        call_id: str,
        agent_id: str,
        status: str,
        duration_seconds: int,
        outcome_notes: str
    ) -> Dict[str, Any]:
        call = db.query(CallRequest).filter(
            CallRequest.id == call_id,
            CallRequest.tenant_id == tenant_id
        ).first()
        if not call:
            raise ValueError("Call request not found")

        call.status = status
        call.assigned_agent_id = agent_id
        call.call_duration_seconds = duration_seconds
        call.call_outcome_notes = outcome_notes
        call.completed_at = datetime.utcnow()
        db.commit()

        return {
            "call_id": call_id,
            "status": status,
            "duration": duration_seconds,
            "notes": outcome_notes,
            "completed_at": call.completed_at.isoformat()
        }
