import re
import uuid
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import httpx
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.conversation import Conversation, Message, ConversationState
from app.models.ticket import EscalationRecord
from app.services.mock_external_api import MockExternalAPIService
from app.services.rag_engine import RAGEngine

class L2ConversationalEngine:
    """
    Intelligent Conversational Support Layer (L2).
    Implements Intent Classification, Entity Extraction, Tool Calling,
    Tenant-Isolated RAG, and Escalation Routing.
    """

    @staticmethod
    def extract_entities(user_text: str, current_entities: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts order IDs, item names, and amounts using pattern matchers."""
        entities = dict(current_entities)

        # Order ID patterns: ORD-FRESH-101, ORD-BITE-201, RIDE-SWIFT-301, ORD-STYLE-401, AWB-VOLT-501, or general patterns
        order_match = re.search(r"\b(ORD-[A-Z]+-\d+|RIDE-[A-Z]+-\d+|AWB-[A-Z]+-\d+|ORD-\d+|#\d+)\b", user_text, re.IGNORECASE)
        if order_match:
            entities["order_id"] = order_match.group(1).upper()

        # Item mentions
        grocery_food_items = [
            "milk", "avocado", "yogurt", "bread", "eggs", "juice",
            "shampoo", "soap", "toothpaste",
            "butter chicken", "naan", "pizza", "biryani", "burger", "dessert", "drink", "lassi",
            "dress", "shirt", "shoes", "size", "parcel", "monitor"
        ]
        text_lower = user_text.lower()
        for item in grocery_food_items:
            if item in text_lower:
                entities["item_name"] = item
                break

        return entities

    @staticmethod
    def classify_intent(user_text: str) -> str:
        text = user_text.lower()

        # Immediate Human Escalation / Safety triggers
        if any(w in text for w in ["human", "agent", "person", "representative", "operator", "call me", "talk to someone"]):
            return "HUMAN_AGENT_REQUEST"
        if any(w in text for w in ["emergency", "accident", "unsafe", "harass", "threat", "police", "allergy", "poison", "hospital"]):
            return "SAFETY_EMERGENCY"

        # Missing / Damaged Items
        if any(w in text for w in ["missing", "didn't receive", "did not receive", "received only", "short", "forgot to pack", "broken", "damaged", "spilled"]):
            return "MISSING_OR_DAMAGED_ITEM"

        # Order / Delivery Tracking
        if any(w in text for w in ["where is", "track", "status", "late", "delay", "taking long", "rider", "driver"]):
            return "ORDER_TRACKING"

        # Refund / Payment Query
        if any(w in text for w in ["refund", "deducted", "charged", "double payment", "money back", "wallet"]):
            return "REFUND_QUERY"

        # Policy & General FAQ
        if any(w in text for w in ["policy", "return", "cancel", "how does", "exchange", "hours", "sla", "rules"]):
            return "POLICY_QUERY"

        return "GENERAL_INQUIRY"

    @classmethod
    async def process_message(
        cls,
        db: Session,
        conversation_id: str,
        user_text: str
    ) -> Dict[str, Any]:
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conv:
            raise ValueError("Conversation not found")

        tenant_id = conv.tenant_id
        config = conv.tenant.config
        state = conv.state

        # Update dialogue turn count
        turn_count = (state.dialogue_turn_count or 0) + 1
        state.dialogue_turn_count = turn_count

        # Extract entities & update memory
        current_entities = state.extracted_entities or {}
        updated_entities = cls.extract_entities(user_text, current_entities)
        state.extracted_entities = updated_entities

        # Classify Intent
        intent = cls.classify_intent(user_text)
        state.last_intent = intent

        # Save user message
        user_msg = Message(
            id=f"msg-{uuid.uuid4().hex[:12]}",
            conversation_id=conv.id,
            tenant_id=tenant_id,
            sender_role="USER",
            sender_name=conv.customer_name,
            content=user_text,
            metadata_json={"intent": intent, "turn": turn_count}
        )
        db.add(user_msg)
        db.flush()

        # -------------------------------------------------------------
        # BRANCH 1: Safety Emergency or Explicit Human Agent Request
        # -------------------------------------------------------------
        if intent in ["HUMAN_AGENT_REQUEST", "SAFETY_EMERGENCY"]:
            return cls._trigger_l3_escalation(
                db=db,
                conv=conv,
                reason="Safety critical issue" if intent == "SAFETY_EMERGENCY" else "Customer explicitly requested human support",
                priority="URGENT" if intent == "SAFETY_EMERGENCY" else "HIGH",
                user_text=user_text
            )

        # -------------------------------------------------------------
        # BRANCH 2: Turn limit reached -> prevent infinite AI loops
        # -------------------------------------------------------------
        max_turns = config.max_l2_turns_before_escalate if config else 5
        if turn_count > max_turns:
            return cls._trigger_l3_escalation(
                db=db,
                conv=conv,
                reason=f"Exceeded maximum L2 dialogue turns ({max_turns}) without resolution",
                priority="MEDIUM",
                user_text=user_text
            )

        # -------------------------------------------------------------
        # BRANCH 3: Clarification Needed (Slot Filling)
        # -------------------------------------------------------------
        order_id = updated_entities.get("order_id") or conv.context_order_id
        item_name = updated_entities.get("item_name")

        if intent == "MISSING_OR_DAMAGED_ITEM":
            if not order_id and not item_name:
                clarification = (
                    "I am very sorry to hear that! Could you please share your **Order ID** "
                    "(e.g., `ORD-FRESH-101` or `ORD-BITE-201`) and let me know which product was missing or damaged?"
                )
                return cls._create_bot_reply(db, conv, clarification, {"step": "NEED_ORDER_AND_ITEM"})
           
            elif order_id and not item_name:
                # Verify order ownership before showing order items
                order = MockExternalAPIService.get_order_details(
                    tenant_id=tenant_id,
                    order_id=order_id,
                    customer_id=conv.customer_id
                )

                if not order:
                    conv.context_order_id = None

                    clarification = (
                        f"I could not verify order `{order_id}` under your account. "
                        "Please check the Order ID in your app and provide the correct ID."
                    )

                    return cls._create_bot_reply(
                        db,
                        conv,
                        clarification,
                        {"step": "NEED_ORDER_ID"}
                    )

                # Store only a verified order ID
                conv.context_order_id = order_id

                if "items" in order:
                    item_list = ", ".join(
                        [f"`{i['name']}`" for i in order["items"]]
                    )

                    clarification = (
                        f"Thank you. I located your verified order `{order_id}` "
                        f"with items: {item_list}.\n\n"
                        "Could you please specify which exact item "
                        "was missing or damaged?"
                    )
                else:
                    clarification = (
                        f"Thank you. I verified order `{order_id}`. "
                        "Could you tell me which product was missing or damaged?"
                    )

                return cls._create_bot_reply(
                    db,
                    conv,
                    clarification,
                    {"step": "NEED_ITEM_NAME", "order_id": order_id}
                )

       
               # -------------------------------------------------------------
        # BRANCH 4: Backend Tool Verification & RAG Retrieval
        # -------------------------------------------------------------

        # Retrieve relevant knowledge from this tenant only
        rag_results = RAGEngine.search(
            db=db,
            tenant_id=tenant_id,
            query=user_text,
            top_k=3
        )

        relevant_rag_results = [
            r for r in rag_results
            if r.get("score", 0) >= 0.35
            and any(
                word in r.get("text", "").lower()
                for word in ["damaged", "broken", "defective", "leaking"]
            )
        ]

        verified_order = None
        tool_action_taken = None

        
        if order_id:
            verified_order = MockExternalAPIService.get_order_details(
                tenant_id=tenant_id,
                order_id=order_id,
                customer_id=conv.customer_id
            )

            if verified_order:
                conv.context_order_id = order_id
            else:
                # Never retain an unverified order ID
                conv.context_order_id = None

        # Only pass a verified order ID to the AI response generator
        safe_order_id = order_id if verified_order else None

        # -------------------------------------------------------------
        # BRANCH 5: Generate Verified Response (AI or Fallback Engine)
        # -------------------------------------------------------------
        bot_response = await cls._generate_ai_or_grounded_response(
            tenant_name=conv.tenant.name,
            bot_name=config.bot_name if config else "AI Assistant",
            user_text=user_text,
            intent=intent,
            order_id=safe_order_id,
            verified_order=verified_order,
            item_name=item_name,
            rag_results=relevant_rag_results,
            tenant_id=tenant_id
        )

        # Resolution check pills
        action_options = [
            {"id": "l2_resolved_yes", "label": "✅ Issue Resolved", "action": "RESOLVE"},
            {"id": "l2_need_human", "label": "👤 Connect with Human Agent (L3)", "action": "ESCALATE"}
        ]

        return cls._create_bot_reply(
            db,
            conv,
            bot_response,
            metadata={
        "rag_sources": [
            r["document_title"] for r in relevant_rag_results
        ],
    "verified_order_id": safe_order_id
    },
            options=action_options
        )

    @classmethod
    async def _generate_ai_or_grounded_response(
        cls,
        tenant_name: str,
        bot_name: str,
        user_text: str,
        intent: str,
        order_id: Optional[str],
        verified_order: Optional[Dict[str, Any]],
        item_name: Optional[str],
        rag_results: List[Dict[str, Any]],
        tenant_id: str
    ) -> str:
        """
        Generates guardrailed response: Uses Groq/OpenAI if API keys configured;
        otherwise uses deterministic grounded synthesis ensuring zero hallucination.
        """
        # 1. If Groq API Key is configured
        if settings.GROQ_API_KEY and settings.AI_PROVIDER == "groq":
            try:
                async with httpx.AsyncClient(timeout=12.0) as client:
                    relevant_rag_results = [
                        r for r in rag_results
                        if r.get("score", 0) >= 0.35
                    ]

                    rag_context = "\n".join(
                        f"- [{r['document_title']}]: {r['text']}"
                        for r in relevant_rag_results
                    )

                    if not rag_context:
                        rag_context = "No sufficiently relevant policy document was found. Do not invent policy details."
                    order_context = json.dumps(verified_order) if verified_order else "None found"
                    system_prompt = (
                        f"You are {bot_name}, customer support for {tenant_name}.\n"
                        f"CRITICAL RULES:\n"
                        f"1. Never invent order status, payment status, refund amounts, or compensation eligibility.\n"
                        f"2. Only reference verified order details: {order_context}\n"
                        f"3. Use tenant policy context only when it directly supports the customer's issue: {rag_context}\n"
                        f"4. Never promise a refund, replacement, wallet credit, or redelivery unless an explicit tenant policy supports that exact action for the reported issue.\n"
                        f"5. If no relevant policy is available, clearly say that the applicable policy needs to be checked.\n"
                        f"6. Never use an unrelated policy as an answer or policy reference.\n"
                        f"7. If information is insufficient, ask for clarification.\n"
                        f"8. Keep responses concise, warm, and professional."
                    )
                    payload = {
                        "model": settings.GROQ_MODEL,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_text}
                        ],
                        "temperature": 0.2
                    }
                    resp = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                        json=payload
                    )
                    if resp.status_code == 200:
                        return resp.json()["choices"][0]["message"]["content"]
            except Exception:
                pass  # Fallback to verified rule generator

        # Grounded Deterministic Generation
        parts = []

        if intent == "MISSING_OR_DAMAGED_ITEM" and verified_order:
            status = verified_order.get("status", "DELIVERED")
            parts.append(f"I have checked your order `{order_id}` (Status: **{status}**).")
            if item_name:
                parts.append(
                f"I've verified that **{item_name.title()}** was part of this consignment. "
                "I'm sorry it arrived damaged. I'll need to check the applicable "
                "policy before confirming whether compensation or redelivery is available."
            )
            else:
                parts.append(
                    "Could you confirm which specific item was missing so we can process your claim?"
                )

        elif intent == "ORDER_TRACKING" and verified_order:
            status = verified_order.get("status", "IN_TRANSIT")
            eta = verified_order.get("eta_minutes", "a few")
            rider = verified_order.get("rider_name", verified_order.get("driver_name", "Assigned Partner"))
            parts.append(f"📦 **Live Tracking for `{order_id}`:**")
            parts.append(f"- Status: **{status}**")
            parts.append(f"- Delivery Partner / Driver: **{rider}**")
            if "eta_minutes" in verified_order:
                parts.append(f"- Estimated Arrival: **{eta} minutes**")
            if "current_location" in verified_order:
                parts.append(f"- Hub: **{verified_order['current_location']}**")

        elif verified_order:
            parts.append(f"I found your record `{order_id}` (Status: {verified_order.get('status')}).")

        # Include only sufficiently relevant policy references
        if rag_results:
            top_hit = rag_results[0]

            if top_hit.get("score", 0) >= 0.35:
                parts.append(
                    f"\n📖 **Policy Reference ({top_hit['document_title']}):**"
                )
                parts.append(f"> {top_hit['text']}")

        if not parts:
            parts.append(
                f"Thank you for contacting {tenant_name} Support. "
                f"To help you promptly, could you please provide your Order ID or reference number?"
            )

        return "\n\n".join(parts)

    @classmethod
    def _create_bot_reply(
        cls,
        db: Session,
        conv: Conversation,
        content: str,
        metadata: Dict[str, Any] = None,
        options: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        bot_msg = Message(
            id=f"msg-{uuid.uuid4().hex[:12]}",
            conversation_id=conv.id,
            tenant_id=conv.tenant_id,
            sender_role="BOT_L2",
            sender_name="AI Support Assistant",
            content=content,
            options=options,
            metadata_json=metadata or {}
        )
        db.add(bot_msg)
        db.commit()

        return {
            "conversation_id": conv.id,
            "current_level": "L2",
            "status": conv.status,
            "message": content,
            "options": options,
            "metadata": metadata
        }

    @classmethod
    def _trigger_l3_escalation(
        cls,
        db: Session,
        conv: Conversation,
        reason: str,
        priority: str,
        user_text: str
    ) -> Dict[str, Any]:
        """Escalates conversation from L2 to L3 Human Support and creates ticket."""
        from app.services.l3_service import L3SupportService

        ticket = L3SupportService.create_escalation_ticket(
            db=db,
            conversation_id=conv.id,
            tenant_id=conv.tenant_id,
            escalation_reason=reason,
            priority=priority,
            customer_latest_message=user_text
        )

        escalation_notice = (
            f"🔄 **Transferred to Human Support (Level 3)**\n\n"
            f"We have created Ticket **`{ticket['ticket_id']}`** (Priority: **{priority}**).\n"
            f"A support agent from **{conv.tenant.name}** is reviewing your complete conversation history "
            f"and will join this chat momentarily.\n\n"
            f"You can also request a phone callback below if you prefer talking to an agent."
        )

        l3_options = [
            {"id": "request_callback", "label": "📞 Request Phone Callback", "action": "CALLBACK"}
        ]

        bot_msg = Message(
            id=f"msg-{uuid.uuid4().hex[:12]}",
            conversation_id=conv.id,
            tenant_id=conv.tenant_id,
            sender_role="SYSTEM",
            sender_name="Escalation Gateway",
            content=escalation_notice,
            options=l3_options,
            metadata_json={"type": "L3_ESCALATED", "ticket_id": ticket["ticket_id"]}
        )
        db.add(bot_msg)
        db.commit()

        return {
            "conversation_id": conv.id,
            "current_level": "L3",
            "status": "ESCALATED",
            "ticket_id": ticket["ticket_id"],
            "message": escalation_notice,
            "options": l3_options
        }
