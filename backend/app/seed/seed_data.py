import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from app.core.config import settings
from app.core.security import get_password_hash
from app.models import (
    Base, Tenant, TenantConfig, User, UserRole, SupportAgent, CustomerProfile,
    IssueCategory, L1Workflow, KnowledgeDocument, KnowledgeChunk
)

def get_sync_db():
    engine = create_engine(settings.SYNC_DATABASE_URL, echo=False)
    Base.metadata.create_all(bind=engine)
    return Session(bind=engine)

def seed_all_tenants():
    db = get_sync_db()
    try:
        # Check if already seeded
        existing_tenants = db.query(Tenant).count()
        if existing_tenants >= 5:
            print(f"Tenants already seeded ({existing_tenants} found). Skipping seed.")
            return

        print("Seeding database with 5 customer tenants, L1 workflows, and RAG knowledge bases...")

        # 1. Create Super Admin
        super_admin = User(
            id=str(uuid.uuid4()),
            email="superadmin@platform.com",
            hashed_password=get_password_hash("SuperAdmin123!"),
            full_name="Global Platform Super Admin",
            role=UserRole.SUPER_ADMIN.value,
            tenant_id=None,
            is_active=True
        )
        db.add(super_admin)

        # Tenant definitions
        tenants_data = [
            {
                "id": "cust-a-freshcart",
                "code": "FRESHCART",
                "name": "FreshCart Quick",
                "industry": "Grocery & Quick Commerce",
                "domain": "freshcart.delivery",
                "config": {
                    "primary_color": "#10B981", # Emerald
                    "accent_color": "#059669",
                    "logo_emoji": "🥕",
                    "bot_name": "FreshCart 10-Min Assistant",
                    "welcome_message": "Hello! Welcome to FreshCart Support. 🥦 Your fresh groceries are our highest priority. How can we assist you today?",
                    "support_email": "help@freshcart.delivery",
                    "support_phone": "+1-800-444-CART",
                    "auto_refund_limit": 30.0,
                    "max_l2_turns_before_escalate": 4
                },
                "admin": {"email": "admin@freshcart.com", "name": "FreshCart Admin"},
                "agents": [
                    {"name": "Aarav Sharma", "email": "aarav@freshcart.com", "dept": "Grocery Escalations", "csat": 4.9},
                    {"name": "Pooja Mehta", "email": "pooja@freshcart.com", "dept": "Cold-Chain Quality", "csat": 4.8}
                ],
                "categories": [
                    {
                        "name": "Missing or Wrong Item",
                        "icon": "box",
                        "order": 1,
                        "requires_order": True,
                        "subcategories": ["Missing dairy / veggies", "Wrong item received", "Expired item received"],
                        "workflow": {
                            "title": "Instant Missing Grocery Compensation",
                            "required_fields": ["order_id", "missing_item_name"],
                            "condition_rules": {"max_delay_hours": 3},
                            "action_type": "REFUND",
                            "max_auto_amount": 25.0,
                            "success": "We have verified your order {order_id}. A refund of ${amount} for the missing {item} has been credited to your FreshCart Wallet.",
                            "fallback": "Because this order value exceeds the automatic threshold, let's transfer you to our specialist for manual approval."
                        }
                    },
                    {
                        "name": "Order Delayed > 15 Mins",
                        "icon": "clock",
                        "order": 2,
                        "requires_order": True,
                        "subcategories": ["Rider stuck at traffic", "Dark store packing delay"],
                        "workflow": {
                            "title": "Delivery Delay Compensation",
                            "required_fields": ["order_id"],
                            "condition_rules": {"min_delay_mins": 10},
                            "action_type": "WALLET_CREDIT",
                            "max_auto_amount": 10.0,
                            "success": "We apologize for the wait. Your rider is 4 minutes away. We have added a $5 credit to your wallet for the delay.",
                            "fallback": "Checking with the dark store manager directly..."
                        }
                    },
                    {
                        "name": "Damaged / Leaking Goods",
                        "icon": "alert-triangle",
                        "order": 3,
                        "requires_order": True,
                        "subcategories": ["Broken glass container", "Crushed eggs / soft fruits", "Leaking milk pouch"],
                        "workflow": {
                            "title": "Damaged Grocery Replacement",
                            "required_fields": ["order_id", "damaged_item"],
                            "condition_rules": {},
                            "action_type": "REPLACEMENT",
                            "max_auto_amount": 20.0,
                            "success": "We've scheduled an immediate replacement rider for {damaged_item}. ETA is 12 minutes.",
                            "fallback": "Connecting with quality inspection team."
                        }
                    },
                    {
                        "name": "Refund & Payment Query",
                        "icon": "credit-card",
                        "order": 4,
                        "requires_order": False,
                        "subcategories": ["Bank deduction without order confirmation", "Wallet balance not showing"],
                        "workflow": None
                    },
                    {
                        "name": "Account & Address Settings",
                        "icon": "user",
                        "order": 5,
                        "requires_order": False,
                        "subcategories": ["Change delivery pin code", "Update phone number"],
                        "workflow": None
                    }
                ],
                "knowledge": [
                    {
                        "title": "FreshCart 10-Minute Cold Chain & Freshness Policy",
                        "doc_type": "POLICY",
                        "content": "FreshCart guarantees that dairy products and ice creams are transported in temperature-controlled insulated bags. Fresh produce has a 4-hour return and replacement window upon delivery. Non-perishable packaged groceries have a 48-hour return window if unopened and seals are intact."
                    },
                    {
                        "title": "FreshCart Refund Timeline & Wallet Credits",
                        "doc_type": "REFUND",
                        "content": "Refunds issued to FreshCart Wallet are instant and can be applied to subsequent orders immediately. Refunds to bank cards or UPI require 2-4 business days depending on the acquiring bank. If an order is delayed past 20 minutes, customers automatically receive a $5 convenience waiver."
                    }
                ]
            },
            {
                "id": "cust-b-biterush",
                "code": "BITERUSH",
                "name": "BiteRush Food",
                "industry": "Food & Restaurant Delivery",
                "domain": "biterush.food",
                "config": {
                    "primary_color": "#EF4444", # Red
                    "accent_color": "#DC2626",
                    "logo_emoji": "🍔",
                    "bot_name": "BiteRush Food Concierge",
                    "welcome_message": "Hey foodie! Welcome to BiteRush Food Support. 🍕 Something wrong with your meal? Let's get it sorted fast!",
                    "support_email": "tasty@biterush.food",
                    "support_phone": "+1-800-BITERUSH",
                    "auto_refund_limit": 25.0,
                    "max_l2_turns_before_escalate": 4
                },
                "admin": {"email": "admin@biterush.com", "name": "BiteRush Admin"},
                "agents": [
                    {"name": "Rahul Verma", "email": "rahul@biterush.com", "dept": "Restaurant Operations", "csat": 4.9},
                    {"name": "Ananya Rao", "email": "ananya@biterush.com", "dept": "Order Quality Specialist", "csat": 4.75}
                ],
                "categories": [
                    {
                        "name": "Spilled Food / Poor Packaging",
                        "icon": "package",
                        "order": 1,
                        "requires_order": True,
                        "subcategories": ["Gravy spilled all over container", "Pizza toppings stuck to lid", "Cold and soggy meal"],
                        "workflow": {
                            "title": "Spilled Dish Refund Guarantee",
                            "required_fields": ["order_id", "dish_name"],
                            "condition_rules": {},
                            "action_type": "REFUND",
                            "max_auto_amount": 25.0,
                            "success": "We're very sorry your meal arrived messy! We have refunded ${amount} for {dish_name} to your BiteRush credits.",
                            "fallback": "Our food safety team is reviewing the restaurant packaging standards."
                        }
                    },
                    {
                        "name": "Missing Dish or Beverage",
                        "icon": "utensils",
                        "order": 2,
                        "requires_order": True,
                        "subcategories": ["Main course missing", "Drink / dessert missing", "Cutlery missing"],
                        "workflow": {
                            "title": "Missing Dish Auto Reimbursement",
                            "required_fields": ["order_id", "missing_dish"],
                            "condition_rules": {},
                            "action_type": "REFUND",
                            "max_auto_amount": 20.0,
                            "success": "The restaurant missed packing your {missing_dish}. We've processed an immediate refund of ${amount}.",
                            "fallback": "Contacting restaurant dispatch to confirm item inventory."
                        }
                    },
                    {
                        "name": "Extreme Delivery Delay",
                        "icon": "clock",
                        "order": 3,
                        "requires_order": True,
                        "subcategories": ["Restaurant taking too long to prepare", "Rider took wrong route"],
                        "workflow": None
                    },
                    {
                        "name": "Dietary / Allergy Concern",
                        "icon": "shield-alert",
                        "order": 4,
                        "requires_order": True,
                        "subcategories": ["Non-veg item received in veg order", "Allergen instruction omitted"],
                        "workflow": None
                    }
                ],
                "knowledge": [
                    {
                        "title": "BiteRush Food Hygiene & Spillage Standards",
                        "doc_type": "POLICY",
                        "content": "BiteRush enforces tamper-proof packaging across all partner restaurants. If more than 30% of a dish is spilled in transit, the dish is eligible for 100% item refund. Orders can be cancelled with 100% refund within 60 seconds of restaurant acceptance."
                    },
                    {
                        "title": "BiteRush Allergen & Dietary Safety Guidelines",
                        "doc_type": "POLICY",
                        "content": "Any report of dietary contamination (such as non-vegetarian items in pure-vegetarian tagged orders or presence of declared allergens like peanuts or gluten) is escalated to high priority L3 support immediately."
                    }
                ]
            },
            {
                "id": "cust-c-swiftride",
                "code": "SWIFTRIDE",
                "name": "SwiftRide Cabs",
                "industry": "Ride-Hailing & Urban Mobility",
                "domain": "swiftride.io",
                "config": {
                    "primary_color": "#F59E0B", # Amber
                    "accent_color": "#D97706",
                    "logo_emoji": "🚕",
                    "bot_name": "SwiftRide Safety & Ride Assistant",
                    "welcome_message": "Hello! Welcome to SwiftRide Mobility Support. 🚖 We are here to ensure safe, comfortable, and fair rides. What can we help with?",
                    "support_email": "safety@swiftride.io",
                    "support_phone": "+1-800-SWIFT-CAB",
                    "auto_refund_limit": 20.0,
                    "max_l2_turns_before_escalate": 3
                },
                "admin": {"email": "admin@swiftride.com", "name": "SwiftRide Admin"},
                "agents": [
                    {"name": "Vikram Singh", "email": "vikram@swiftride.com", "dept": "Mobility Safety & Disputes", "csat": 4.95},
                    {"name": "Sneha Iyer", "email": "sneha@swiftride.com", "dept": "Fare Audits", "csat": 4.88}
                ],
                "categories": [
                    {
                        "name": "Fare & Toll Dispute",
                        "icon": "dollar-sign",
                        "order": 1,
                        "requires_order": True,
                        "subcategories": ["Driver took long detour", "Incorrect airport toll charged", "Waiting charges disputed"],
                        "workflow": {
                            "title": "GPS Route & Toll Recalculation",
                            "required_fields": ["order_id", "dispute_reason"],
                            "condition_rules": {"max_variance_percent": 25},
                            "action_type": "FARE_ADJUSTMENT",
                            "max_auto_amount": 15.0,
                            "success": "Our GPS audit confirmed an unnecessary detour on ride {order_id}. We have adjusted your fare and refunded ${amount}.",
                            "fallback": "Route telemetry requires agent verification."
                        }
                    },
                    {
                        "name": "Lost Item in Cab",
                        "icon": "search",
                        "order": 2,
                        "requires_order": True,
                        "subcategories": ["Phone left on back seat", "Wallet / bag left in trunk"],
                        "workflow": {
                            "title": "Driver Call Masking for Lost Item",
                            "required_fields": ["order_id", "item_description"],
                            "condition_rules": {},
                            "action_type": "DRIVER_CALL_BRIDGE",
                            "max_auto_amount": 0.0,
                            "success": "We've established a secure 2-hour masked calling link to your driver for ride {order_id}. You can call without sharing private numbers.",
                            "fallback": "Connecting with local lost and found desk."
                        }
                    },
                    {
                        "name": "Driver Demanded Extra Cash",
                        "icon": "alert-circle",
                        "order": 3,
                        "requires_order": True,
                        "subcategories": ["Demanded cash despite online payment", "Refused AC without tip"],
                        "workflow": None
                    },
                    {
                        "name": "Safety or Unsafe Driving",
                        "icon": "shield-alert",
                        "order": 4,
                        "requires_order": True,
                        "subcategories": ["Reckless driving / speeding", "Verbal altercation"],
                        "workflow": None
                    }
                ],
                "knowledge": [
                    {
                        "title": "SwiftRide Upfront Pricing & Route Recalculation",
                        "doc_type": "POLICY",
                        "content": "SwiftRide fares are calculated based on upfront estimated distance and duration. If a driver takes a detour that increases trip length by more than 15% without passenger consent, the customer is entitled to an automatic fare rollback."
                    },
                    {
                        "title": "SwiftRide Lost Property Retrieval Policy",
                        "doc_type": "POLICY",
                        "content": "Drivers are contractually bound to safeguard items left in cabs. When reported within 24 hours, SwiftRide provides a secure masked proxy phone number to reach the driver directly. Return delivery fare can be reimbursed up to $15."
                    }
                ]
            },
            {
                "id": "cust-d-stylenova",
                "code": "STYLENOVA",
                "name": "StyleNova Retail",
                "industry": "Fashion & Lifestyle E-Commerce",
                "domain": "stylenova.fashion",
                "config": {
                    "primary_color": "#8B5CF6", # Purple
                    "accent_color": "#7C3AED",
                    "logo_emoji": "👗",
                    "bot_name": "StyleNova Fashion Stylist & Support",
                    "welcome_message": "Welcome to StyleNova! 👠 Looking for size exchanges, return pickups, or order tracking? We're here to help you look your best!",
                    "support_email": "care@stylenova.fashion",
                    "support_phone": "+1-800-STYLENOVA",
                    "auto_refund_limit": 50.0,
                    "max_l2_turns_before_escalate": 4
                },
                "admin": {"email": "admin@stylenova.com", "name": "StyleNova Admin"},
                "agents": [
                    {"name": "Priya Kapoor", "email": "priya@stylenova.com", "dept": "Apparel Returns & Exchange", "csat": 4.91},
                    {"name": "Karan Joshi", "email": "karan@stylenova.com", "dept": "Logistics & Pickups", "csat": 4.82}
                ],
                "categories": [
                    {
                        "name": "Size Exchange or Color Swap",
                        "icon": "refresh-cw",
                        "order": 1,
                        "requires_order": True,
                        "subcategories": ["Size too tight", "Size too loose", "Need different color"],
                        "workflow": {
                            "title": "Free Doorstep Size Exchange",
                            "required_fields": ["order_id", "desired_size"],
                            "condition_rules": {"within_days": 15},
                            "action_type": "EXCHANGE_BOOKING",
                            "max_auto_amount": 60.0,
                            "success": "Your exchange for size {desired_size} on order {order_id} has been booked! The courier will deliver the new size and collect the old item simultaneously.",
                            "fallback": "Item out of stock in requested size; offering instant store credit."
                        }
                    },
                    {
                        "name": "Return Pickup Delay",
                        "icon": "truck",
                        "order": 2,
                        "requires_order": True,
                        "subcategories": ["Courier did not show up", "Pickup rescheduled without notice"],
                        "workflow": None
                    },
                    {
                        "name": "Refund Not Credited",
                        "icon": "credit-card",
                        "order": 3,
                        "requires_order": True,
                        "subcategories": ["Item picked up 5 days ago", "Bank account refund pending"],
                        "workflow": None
                    }
                ],
                "knowledge": [
                    {
                        "title": "StyleNova 15-Day Doorstep Exchange Guarantee",
                        "doc_type": "POLICY",
                        "content": "Customers can exchange any apparel item for a different size or color within 15 days of delivery, provided original tags are intact and garments are unwashed. Handbags, footwear, and accessories must include original branded packaging."
                    },
                    {
                        "title": "StyleNova Reverse Logistics & Refund Timelines",
                        "doc_type": "REFUND",
                        "content": "Refunds are triggered automatically within 4 hours of the courier scanning the return pickup package at the doorstep. Store credits appear immediately; card refunds reflect in 3-5 bank business days."
                    }
                ]
            },
            {
                "id": "cust-e-voltexpress",
                "code": "VOLTEXPRESS",
                "name": "VoltExpress Logistics",
                "industry": "B2B & Hyperlocal Parcel Logistics",
                "domain": "voltexpress.delivery",
                "config": {
                    "primary_color": "#06B6D4", # Cyan
                    "accent_color": "#0891B2",
                    "logo_emoji": "📦",
                    "bot_name": "VoltExpress Cargo Bot",
                    "welcome_message": "Welcome to VoltExpress Logistics. 🚚 Real-time tracking, delivery rescheduling, and proof-of-delivery verification.",
                    "support_email": "dispatch@voltexpress.delivery",
                    "support_phone": "+1-800-VOLT-LOG",
                    "auto_refund_limit": 40.0,
                    "max_l2_turns_before_escalate": 4
                },
                "admin": {"email": "admin@voltexpress.com", "name": "VoltExpress Admin"},
                "agents": [
                    {"name": "Deepak Nair", "email": "deepak@voltexpress.com", "dept": "B2B Freight & Transit", "csat": 4.93},
                    {"name": "Divya Sen", "email": "divya@voltexpress.com", "dept": "Consignment Disputes", "csat": 4.87}
                ],
                "categories": [
                    {
                        "name": "Reschedule Delivery / Change Address",
                        "icon": "map-pin",
                        "order": 1,
                        "requires_order": True,
                        "subcategories": ["Change delivery date to tomorrow", "Change recipient contact number", "Deliver to neighbor"],
                        "workflow": {
                            "title": "Consignment Manifest Rescheduling",
                            "required_fields": ["order_id", "new_date_or_instructions"],
                            "condition_rules": {"status_in": ["IN_TRANSIT", "OUT_FOR_DELIVERY"]},
                            "action_type": "RESCHEDULE_DELIVERY",
                            "max_auto_amount": 0.0,
                            "success": "Consignment {order_id} has been rescheduled to your requested slot. The delivery manifest is updated.",
                            "fallback": "Shipment is already out for final delivery attempt; contacting courier vehicle driver."
                        }
                    },
                    {
                        "name": "Proof of Delivery (POD) Dispute",
                        "icon": "file-check",
                        "order": 2,
                        "requires_order": True,
                        "subcategories": ["Marked delivered but not received", "Signature does not match recipient"],
                        "workflow": None
                    },
                    {
                        "name": "Damaged Cargo Claim",
                        "icon": "alert-octagon",
                        "order": 3,
                        "requires_order": True,
                        "subcategories": ["Outer carton crushed", "Perishable cargo temperature violation"],
                        "workflow": None
                    }
                ],
                "knowledge": [
                    {
                        "title": "VoltExpress Express Transit SLA & Guarantees",
                        "doc_type": "POLICY",
                        "content": "VoltExpress guarantees same-day delivery for intra-city express bookings placed before 11:00 AM. Inter-city freight operates on a 48-hour hub-and-spoke transit schedule. Any delay beyond 24 hours of scheduled SLA qualifies for 20% freight cost waiver."
                    },
                    {
                        "title": "VoltExpress Proof-of-Delivery (POD) Security",
                        "doc_type": "POLICY",
                        "content": "All high-value packages require an OTP confirmation or recipient biometric/digital signature upon handover. If an item is disputed as undelivered despite a delivered status, an investigation with driver GPS geo-tagging is initiated within 2 hours."
                    }
                ]
            }
        ]

        # Insert Tenants, Configs, Users, Categories, Workflows, Knowledge
        for t_data in tenants_data:
            tenant = Tenant(
                id=t_data["id"],
                code=t_data["code"],
                name=t_data["name"],
                industry=t_data["industry"],
                domain=t_data["domain"],
                is_active=True
            )
            db.add(tenant)
            db.flush()

            cfg = t_data["config"]
            config = TenantConfig(
                id=str(uuid.uuid4()),
                tenant_id=tenant.id,
                primary_color=cfg["primary_color"],
                accent_color=cfg["accent_color"],
                logo_emoji=cfg["logo_emoji"],
                bot_name=cfg["bot_name"],
                welcome_message=cfg["welcome_message"],
                support_email=cfg["support_email"],
                support_phone=cfg["support_phone"],
                auto_refund_limit=cfg["auto_refund_limit"],
                max_l2_turns_before_escalate=cfg["max_l2_turns_before_escalate"]
            )
            db.add(config)

            # Tenant Admin User
            adm = t_data["admin"]
            admin_user = User(
                id=str(uuid.uuid4()),
                email=adm["email"],
                hashed_password=get_password_hash("Admin123!"),
                full_name=adm["name"],
                role=UserRole.TENANT_ADMIN.value,
                tenant_id=tenant.id,
                is_active=True
            )
            db.add(admin_user)
            db.flush()

            # Support Agents
            for ag in t_data["agents"]:
                agent_user = User(
                    id=str(uuid.uuid4()),
                    email=ag["email"],
                    hashed_password=get_password_hash("Agent123!"),
                    full_name=ag["name"],
                    role=UserRole.SUPPORT_AGENT.value,
                    tenant_id=tenant.id,
                    is_active=True
                )
                db.add(agent_user)
                db.flush()

                support_agent = SupportAgent(
                    id=f"agent-{tenant.code.lower()}-{ag['name'].split()[0].lower()}",
                    tenant_id=tenant.id,
                    user_id=agent_user.id,
                    display_name=ag["name"],
                    department=ag["dept"],
                    is_online=True,
                    average_csat=ag["csat"],
                    max_tickets=12
                )
                db.add(support_agent)

            # Issue Categories & Workflows
            for cat in t_data["categories"]:
                category = IssueCategory(
                    id=f"cat-{tenant.code.lower()}-{cat['name'].lower().replace(' ', '-').replace('/', '-')[:30]}",
                    tenant_id=tenant.id,
                    name=cat["name"],
                    icon=cat["icon"],
                    display_order=cat["order"],
                    requires_order=cat["requires_order"]
                )
                db.add(category)
                db.flush()

                # Subcategories
                for idx, sub_name in enumerate(cat["subcategories"]):
                    subcat = IssueCategory(
                        id=f"subcat-{tenant.code.lower()}-{idx}-{sub_name.lower().replace(' ', '-')[:25]}",
                        tenant_id=tenant.id,
                        parent_id=category.id,
                        name=sub_name,
                        icon="corner-down-right",
                        display_order=idx + 1,
                        requires_order=cat["requires_order"]
                    )
                    db.add(subcat)

                # Workflow if configured
                wf_data = cat.get("workflow")
                if wf_data:
                    workflow = L1Workflow(
                        id=f"wf-{tenant.code.lower()}-{category.id[:20]}",
                        tenant_id=tenant.id,
                        category_id=category.id,
                        title=wf_data["title"],
                        required_fields=wf_data["required_fields"],
                        condition_rules=wf_data["condition_rules"],
                        automated_action_type=wf_data["action_type"],
                        max_auto_amount=wf_data["max_auto_amount"],
                        success_response_template=wf_data["success"],
                        fallback_response_template=wf_data["fallback"]
                    )
                    db.add(workflow)

            # Knowledge Documents & Chunks
            for doc_info in t_data["knowledge"]:
                doc = KnowledgeDocument(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant.id,
                    title=doc_info["title"],
                    doc_type=doc_info["doc_type"],
                    content=doc_info["content"]
                )
                db.add(doc)
                db.flush()

                # Add chunks
                chunk = KnowledgeChunk(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant.id,
                    document_id=doc.id,
                    chunk_index=0,
                    chunk_text=doc_info["content"],
                    metadata_json={"title": doc_info["title"], "type": doc_info["doc_type"]}
                )
                db.add(chunk)

        db.commit()
        print("Successfully seeded all 5 tenants, workflows, agents, and knowledge bases!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_all_tenants()
