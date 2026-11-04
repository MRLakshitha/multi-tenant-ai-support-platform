
import uuid
from typing import Dict, Any
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.category import IssueCategory
from app.models.l1_workflow import L1Workflow, L1Action
from app.models.conversation import Conversation, Message, ConversationState
from app.models.ticket import EscalationRecord
from app.services.mock_external_api import MockExternalAPIService


class L1Engine:
    """
    Deterministic rule-based automated support engine.

    Handles:
    - Conversation initialization
    - Category and subcategory selection
    - Customer-owned order verification
    - Automated mock refund processing
    - Resolution confirmation
    - CSAT collection
    - L1 to L2 escalation
    """

    @staticmethod
    def start_conversation(
        db: Session,
        tenant_id: str,
        customer_id: str,
        customer_name: str = "Customer"
    ) -> Dict[str, Any]:

        tenant = db.query(Tenant).filter(
            Tenant.id == tenant_id
        ).first()

        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        if not customer_id or not customer_id.strip():
            raise ValueError("Customer ID is required")

        config = tenant.config

        welcome_text = (
            config.welcome_message
            if config
            else f"Hello! Welcome to {tenant.name} Support. How can I help you today?"
        )

        # Create conversation
        conv_id = f"conv-{uuid.uuid4().hex[:12]}"

        conversation = Conversation(
            id=conv_id,
            tenant_id=tenant_id,
            customer_id=customer_id.strip(),
            customer_name=customer_name,
            current_level="L1",
            status="ACTIVE",
            created_at=datetime.utcnow()
        )

        db.add(conversation)

        # Create conversation state
        state = ConversationState(
            id=str(uuid.uuid4()),
            conversation_id=conv_id,
            tenant_id=tenant_id,
            extracted_entities={},
            dialogue_turn_count=0,
            last_intent=None,
            state_payload={"step": "CATEGORY_SELECTION"}
        )

        db.add(state)

        # Retrieve top-level categories
        categories = db.query(IssueCategory).filter(
            IssueCategory.tenant_id == tenant_id,
            IssueCategory.parent_id == None,
            IssueCategory.is_active == True
        ).order_by(
            IssueCategory.display_order
        ).all()

        category_options = [
            {
                "id": c.id,
                "label": c.name,
                "icon": c.icon,
                "requires_order": c.requires_order
            }
            for c in categories
        ]

        # Add welcome message
        welcome_msg = Message(
            id=f"msg-{uuid.uuid4().hex[:12]}",
            conversation_id=conv_id,
            tenant_id=tenant_id,
            sender_role="BOT_L1",
            sender_name=config.bot_name if config else "Support Assistant",
            content=welcome_text,
            options=category_options,
            metadata_json={"type": "WELCOME_OPTIONS"}
        )

        db.add(welcome_msg)
        db.commit()

        return {
            "conversation_id": conv_id,
            "tenant_id": tenant_id,
            "current_level": "L1",
            "bot_name": config.bot_name if config else "Support Assistant",
            "message": welcome_text,
            "options": category_options
        }

    @staticmethod
    def handle_option_selection(
        db: Session,
        conversation_id: str,
        category_id: str
    ) -> Dict[str, Any]:

        conv = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()

        if not conv:
            raise ValueError("Conversation not found")

        tenant_id = conv.tenant_id

        category = db.query(IssueCategory).filter(
            IssueCategory.id == category_id,
            IssueCategory.tenant_id == tenant_id
        ).first()

        if not category:
            raise ValueError("Category not found for this tenant")

        # Validate subcategory selection when one is required
        state_payload = (
            conv.state.state_payload
            if conv.state and conv.state.state_payload
            else {}
        )

        if state_payload.get("step") == "AWAITING_SUBCATEGORY":
            expected_parent_id = state_payload.get("parent_category_id")

            if category.parent_id != expected_parent_id:
                raise ValueError(
                    "Please select a valid subcategory from the options provided."
                )

        conv.selected_category_id = category.id

        # Record user selection
        user_msg = Message(
            id=f"msg-{uuid.uuid4().hex[:12]}",
            conversation_id=conv.id,
            tenant_id=tenant_id,
            sender_role="USER",
            sender_name=conv.customer_name,
            content=category.name,
            options=None,
            metadata_json={"selected_category_id": category.id}
        )

        db.add(user_msg)

        # Check for subcategories
        subcategories = db.query(IssueCategory).filter(
            IssueCategory.parent_id == category.id,
            IssueCategory.tenant_id == tenant_id,
            IssueCategory.is_active == True
        ).order_by(
            IssueCategory.display_order
        ).all()

        if subcategories:
            if conv.state:
                conv.state.state_payload = {
                    "step": "AWAITING_SUBCATEGORY",
                    "parent_category_id": category.id
                }
            sub_options = [
                {
                    "id": s.id,
                    "label": s.name,
                    "icon": s.icon,
                    "requires_order": s.requires_order
                }
                for s in subcategories
            ]

            bot_reply = Message(
                id=f"msg-{uuid.uuid4().hex[:12]}",
                conversation_id=conv.id,
                tenant_id=tenant_id,
                sender_role="BOT_L1",
                sender_name=(
                    conv.tenant.config.bot_name
                    if conv.tenant and conv.tenant.config
                    else "Support Assistant"
                ),
                content=f"Please select the specific issue regarding **{category.name}**:",
                options=sub_options,
                metadata_json={
                    "type": "SUBCATEGORY_SELECTION",
                    "parent_id": category.id
                }
            )

            db.add(bot_reply)
            db.commit()

            return {
                "conversation_id": conv.id,
                "current_level": "L1",
                "message": bot_reply.content,
                "options": sub_options
            }

                # Check whether this category or its parent requires an order ID
        parent_category = None

        if category.parent_id:
            parent_category = db.query(IssueCategory).filter(
                IssueCategory.id == category.parent_id,
                IssueCategory.tenant_id == tenant_id
            ).first()

        requires_order = (
            category.requires_order
            or (
                parent_category is not None
                and parent_category.requires_order
            )
        )

        # Ask for order ID when required
        if requires_order:
            bot_text = (
                f"To assist with **{category.name}**, please provide your Order ID / Reference ID "
                f"(e.g., ORD-FRESH-101, ORD-BITE-201, RIDE-SWIFT-301, ORD-STYLE-401, or AWB-VOLT-501):"
            )

            bot_reply = Message(
                id=f"msg-{uuid.uuid4().hex[:12]}",
                conversation_id=conv.id,
                tenant_id=tenant_id,
                sender_role="BOT_L1",
                sender_name="Support Assistant",
                content=bot_text,
                options=None,
                metadata_json={
                    "type": "INPUT_REQUIRED",
                    "field": "order_id"
                }
            )

            db.add(bot_reply)

            conv.state.state_payload = {
                "step": "AWAITING_ORDER_ID",
                "category_id": category.id,
                "parent_category_id": (
                    parent_category.id if parent_category else category.id
                )
            }
            db.commit()

            return {
                "conversation_id": conv.id,
                "current_level": "L1",
                "message": bot_text,
                "awaiting_input": "order_id"
            }

        # Check automated workflow
        workflow = db.query(L1Workflow).filter(
            L1Workflow.category_id == category.id,
            L1Workflow.tenant_id == tenant_id,
            L1Workflow.is_active == True
        ).first()

        response_text = (
            workflow.success_response_template
            if workflow
            else f"Thank you for reaching out regarding **{category.name}**. We've recorded your inquiry."
        )

        resolution_options = [
            {
                "id": "resolved_yes",
                "label": "✅ Yes, my issue is resolved",
                "action": "RESOLVE"
            },
            {
                "id": "resolved_no",
                "label": "❌ No, I need further assistance",
                "action": "ESCALATE"
            }
        ]

        bot_reply = Message(
            id=f"msg-{uuid.uuid4().hex[:12]}",
            conversation_id=conv.id,
            tenant_id=tenant_id,
            sender_role="BOT_L1",
            sender_name="Support Assistant",
            content=f"{response_text}\n\n**Is your issue resolved?**",
            options=resolution_options,
            metadata_json={"type": "RESOLUTION_CHECK"}
        )

        db.add(bot_reply)
        db.commit()

        return {
            "conversation_id": conv.id,
            "current_level": "L1",
            "message": bot_reply.content,
            "options": resolution_options
        }

    @staticmethod
    def handle_order_input(
        db: Session,
        conversation_id: str,
        input_text: str
    ) -> Dict[str, Any]:

        conv = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()

        if not conv:
            raise ValueError("Conversation not found")

        tenant_id = conv.tenant_id

        # Validate the conversation workflow state before accepting an order ID
        state_payload = (
            conv.state.state_payload
            if conv.state and conv.state.state_payload
            else {}
        )

        if state_payload.get("step") != "AWAITING_ORDER_ID":
            raise ValueError(
                "Please select your issue category and subcategory before entering an Order ID."
            )

        expected_category_id = state_payload.get("category_id")

        if not expected_category_id or conv.selected_category_id != expected_category_id:
            raise ValueError(
                "Your issue selection is incomplete. Please select your issue again."
            )

        order_id = input_text.strip().upper()

        if not order_id:
            raise ValueError("Order ID cannot be empty")

        # Record user message
        user_msg = Message(
            id=f"msg-{uuid.uuid4().hex[:12]}",
            conversation_id=conv.id,
            tenant_id=tenant_id,
            sender_role="USER",
            sender_name=conv.customer_name,
            content=input_text,
            options=None,
            metadata_json={"provided_order_id": order_id}
        )

        db.add(user_msg)

        # Verify tenant, order ID and customer ownership
        order = MockExternalAPIService.get_order_details(
            tenant_id=tenant_id,
            order_id=order_id,
            customer_id=conv.customer_id
        )

        if not order:

            # Do not retain an unverified order ID
            conv.context_order_id = None

            bot_text = (
                f"We could not find an active order with ID `{order_id}` under your account. "
                f"Please verify the number from your app receipts, or choose an option below:"
            )

            escalate_options = [
                {
                    "id": "reenter_order",
                    "label": "🔄 Re-enter Order ID",
                    "action": "RETRY"
                },
                {
                    "id": "resolved_no",
                    "label": "💬 Speak with AI / Human Support",
                    "action": "ESCALATE"
                }
            ]

            bot_reply = Message(
                id=f"msg-{uuid.uuid4().hex[:12]}",
                conversation_id=conv.id,
                tenant_id=tenant_id,
                sender_role="BOT_L1",
                sender_name="Support Assistant",
                content=bot_text,
                options=escalate_options,
                metadata_json={"type": "ORDER_NOT_FOUND"}
            )

            db.add(bot_reply)
            db.commit()

            return {
                "conversation_id": conv.id,
                "current_level": "L1",
                "message": bot_text,
                "options": escalate_options
            }

        # Store only a verified order ID
        conv.context_order_id = order_id

               # Verified order found — do not execute any action automatically

        status_str = order.get("status", "CONFIRMED")
        total_paid = float(
            order.get("total_paid", order.get("actual_fare", 15.0))
        )

        state_payload = (
            conv.state.state_payload
            if conv.state and conv.state.state_payload
            else {}
        )

        # Workflows are attached to the parent category
        workflow_category_id = state_payload.get(
            "parent_category_id",
            conv.selected_category_id
        )

        workflow = db.query(L1Workflow).filter(
            L1Workflow.category_id == workflow_category_id,
            L1Workflow.tenant_id == tenant_id,
            L1Workflow.is_active == True
        ).first()

        selected_category = db.query(IssueCategory).filter(
            IssueCategory.id == conv.selected_category_id,
            IssueCategory.tenant_id == tenant_id
        ).first()

        category_name = (
            selected_category.name
            if selected_category
            else "General Support"
        )
        
        action_executed = False

        if workflow:
            configured_action = (
                workflow.automated_action_type or "MANUAL_REVIEW"
            )

            action_summary = (
                f"**Verified Order Details:**\n"
                f"- Order ID: `{order_id}`\n"
                f"- Status: `{status_str}`\n"
                f"- Total: `${total_paid:.2f}`\n"
                f"- Selected issue: **{category_name}**\n\n"
                f"**Matching Support Workflow:** {workflow.title}\n"
                f"Configured action: `{configured_action}`\n\n"
                f"Your order has been verified. No refund, replacement, "
                f"or wallet credit has been executed automatically. "
                f"The requested resolution requires the appropriate "
                f"workflow checks and confirmation."
            )
        else:
            action_summary = (
                f"**Verified Order Details:**\n"
                f"- Order ID: `{order_id}`\n"
                f"- Status: `{status_str}`\n"
                f"- Total: `${total_paid:.2f}`\n"
                f"- Selected issue: **{category_name}**\n\n"
                f"We couldn't find an active automated workflow for "
                f"this issue. Your order is verified and can be reviewed "
                f"by our support team. No automatic action was executed."
            )

        # Save the verified order and pending workflow information
        if conv.state:
            conv.state.state_payload = {
                **state_payload,
                "step": "AWAITING_RESOLUTION_CONFIRMATION",
                "order_id": order_id,
                "workflow_id": workflow.id if workflow else None
            }

        resolution_options = [
            {
                "id": "resolved_no",
                "label": "Connect me with support",
                "action": "ESCALATE"
            }
        ]

        full_message = action_summary

        bot_reply = Message(
            id=f"msg-{uuid.uuid4().hex[:12]}",
            conversation_id=conv.id,
            tenant_id=tenant_id,
            sender_role="BOT_L1",
            sender_name="Support Assistant",
            content=full_message,
            options=resolution_options,
            metadata_json={
                "type": "RESOLUTION_CHECK",
                "action_executed": action_executed
            }
        )

        db.add(bot_reply)
        db.commit()

        return {
            "conversation_id": conv.id,
            "current_level": "L1",
            "message": full_message,
            "options": resolution_options
        }

    @staticmethod
    def handle_resolution_confirmation(
        db: Session,
        conversation_id: str,
        resolved: bool
    ) -> Dict[str, Any]:

        conv = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()

        if not conv:
            raise ValueError("Conversation not found")

        tenant_id = conv.tenant_id

        # Log customer answer
        user_choice = (
            "Yes, my issue is resolved."
            if resolved
            else "No, I need further assistance."
        )

        user_msg = Message(
            id=f"msg-{uuid.uuid4().hex[:12]}",
            conversation_id=conv.id,
            tenant_id=tenant_id,
            sender_role="USER",
            sender_name=conv.customer_name,
            content=user_choice,
            options=None,
            metadata_json={"resolved_choice": resolved}
        )

        db.add(user_msg)

        if resolved:

            # Close conversation as resolved at L1
            conv.status = "RESOLVED"
            conv.resolution_level = "L1"
            conv.closed_at = datetime.utcnow()

            close_text = (
                "Glad we could help resolve your issue! 🎉\n"
                "How would you rate your support experience today? (1 to 5 stars)"
            )

            csat_options = [
                {"id": "csat_5", "label": "⭐ 5 - Excellent", "rating": 5},
                {"id": "csat_4", "label": "⭐ 4 - Good", "rating": 4},
                {"id": "csat_3", "label": "⭐ 3 - Okay", "rating": 3},
                {"id": "csat_2", "label": "⭐ 2 - Poor", "rating": 2},
                {"id": "csat_1", "label": "⭐ 1 - Terrible", "rating": 1}
            ]

            bot_reply = Message(
                id=f"msg-{uuid.uuid4().hex[:12]}",
                conversation_id=conv.id,
                tenant_id=tenant_id,
                sender_role="BOT_L1",
                sender_name="Support Assistant",
                content=close_text,
                options=csat_options,
                metadata_json={"type": "CSAT_PROMPT"}
            )

            db.add(bot_reply)
            db.commit()

            return {
                "conversation_id": conv.id,
                "current_level": "L1",
                "status": "RESOLVED",
                "message": close_text,
                "options": csat_options
            }

        else:

            # Unresolved -> Escalate to L2
            conv.current_level = "L2"

            esc = EscalationRecord(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                conversation_id=conv.id,
                from_level="L1",
                to_level="L2",
                reason="Customer indicated issue was unresolved via predefined L1 rules",
                created_at=datetime.utcnow()
            )

            db.add(esc)

            l2_intro = (
                "Understood. I am transferring you to our **AI Conversational Specialist (L2)**. 🤖\n\n"
                "Please describe your problem in your own words. For example:\n"
                "_'I ordered three items, but only two arrived. What should I do?'_"
            )

            bot_reply = Message(
                id=f"msg-{uuid.uuid4().hex[:12]}",
                conversation_id=conv.id,
                tenant_id=tenant_id,
                sender_role="BOT_L2",
                sender_name="AI Support Assistant",
                content=l2_intro,
                options=None,
                metadata_json={
                    "type": "L2_HANDOFF",
                    "escalated_from": "L1"
                }
            )

            db.add(bot_reply)
            db.commit()

            return {
                "conversation_id": conv.id,
                "current_level": "L2",
                "status": "ACTIVE",
                "message": l2_intro,
                "options": None
            }
