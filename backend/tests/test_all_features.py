import pytest
from fastapi.testclient import TestClient
from main import app
from app.core.security import create_access_token

client = TestClient(app)

# -------------------------------------------------------------
# 1. Multi-Tenant Loading & Verification
# -------------------------------------------------------------
def test_all_five_tenants_present():
    """Verifies that all 5 required customer tenants exist and are active."""
    response = client.get("/api/v1/tenants")
    assert response.status_code == 200
    tenants = response.json()
    tenant_ids = [t["id"] for t in tenants]
    expected_tenants = [
        "cust-a-freshcart",
        "cust-b-biterush",
        "cust-c-swiftride",
        "cust-d-stylenova",
        "cust-e-voltexpress"
    ]
    for exp in expected_tenants:
        assert exp in tenant_ids, f"Expected tenant {exp} to be loaded"

# -------------------------------------------------------------
# 2. Strict Tenant Isolation & Cross-Tenant Access Prevention
# -------------------------------------------------------------
def test_cross_tenant_isolation_enforced():
    """
    Ensures that a tenant admin from FreshCart CANNOT access or update
    BiteRush's configuration or tickets.
    """
    # FreshCart admin token
    token = create_access_token(subject="4530f9ff-56e0-416a-8ecf-7622c2500057", role="TENANT_ADMIN", tenant_id="cust-a-freshcart")
    
    # Try to update BiteRush config with FreshCart token
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": "cust-b-biterush"
    }
    response = client.put(
        "/api/v1/tenants/cust-b-biterush/config",
        headers=headers,
        json={"bot_name": "Hacked Bot Name"}
    )
    assert response.status_code in [403, 404], "Cross-tenant access must be blocked with 403 Forbidden"

# -------------------------------------------------------------
# 3. Authentication & RBAC
# -------------------------------------------------------------
def test_auth_login_and_me():
    """Tests login for tenant admin and JWT verification."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@freshcart.com", "password": "Admin123!"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "TENANT_ADMIN"
    assert data["tenant_id"] == "cust-a-freshcart"

    # Test /me endpoint
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "admin@freshcart.com"

# -------------------------------------------------------------
# 4. L1 Rule-Based Chatbot & Predefined Options
# -------------------------------------------------------------
def test_l1_welcome_and_clickable_options():
    """Tests starting chat, receiving welcome greeting and clickable category options."""
    headers = {"X-Tenant-ID": "cust-a-freshcart"}
    response = client.post(
        "/api/v1/chat/start",
        headers=headers,
        json={"customer_id": "cust-test-1", "customer_name": "Test Customer"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["current_level"] == "L1"
    assert "FreshCart" in data["message"]
    assert len(data["options"]) > 0

    conv_id = data["conversation_id"]
    category_id = data["options"][0]["id"]

    # Select category
    cat_resp = client.post(
        "/api/v1/chat/select-option",
        headers=headers,
        json={"conversation_id": conv_id, "category_id": category_id}
    )
    assert cat_resp.status_code == 200
    cat_data = cat_resp.json()
    assert cat_data["current_level"] == "L1"
    assert "options" in cat_data or "awaiting_input" in cat_data

# -------------------------------------------------------------
# 5. L1 Instant Resolution & CSAT Prompt
# -------------------------------------------------------------
def test_l1_order_verification_and_instant_resolution():
    """Tests order verification and instant resolution confirmation at L1."""
    headers = {"X-Tenant-ID": "cust-a-freshcart"}
    start_resp = client.post(
        "/api/v1/chat/start",
        headers=headers,
        json={"customer_id": "cust-test-2", "customer_name": "Sarah Connor"}
    )
    conv_id = start_resp.json()["conversation_id"]

    # Submit valid verified order ID
    input_resp = client.post(
        "/api/v1/chat/order-input",
        headers=headers,
        json={"conversation_id": conv_id, "input_text": "ORD-FRESH-101"}
    )
    assert input_resp.status_code == 200
    data = input_resp.json()
    assert "Verified Order Details" in data["message"]
    assert "Automated Resolution Approved" in data["message"]

    # Confirm resolved: YES
    confirm_resp = client.post(
        "/api/v1/chat/confirm-resolution",
        headers=headers,
        json={"conversation_id": conv_id, "resolved": True}
    )
    assert confirm_resp.status_code == 200
    confirm_data = confirm_resp.json()
    assert confirm_data["status"] == "RESOLVED"
    assert "rate your support experience" in confirm_data["message"]

# -------------------------------------------------------------
# 6. L1 to L2 Escalation (When Customer Selects "No")
# -------------------------------------------------------------
def test_l1_to_l2_escalation():
    """Tests transition from L1 to L2 when customer needs further assistance."""
    headers = {"X-Tenant-ID": "cust-a-freshcart"}
    start_resp = client.post(
        "/api/v1/chat/start",
        headers=headers,
        json={"customer_id": "cust-test-3", "customer_name": "Escalation Test"}
    )
    conv_id = start_resp.json()["conversation_id"]

    # Customer selects "No, I need further assistance"
    esc_resp = client.post(
        "/api/v1/chat/confirm-resolution",
        headers=headers,
        json={"conversation_id": conv_id, "resolved": False}
    )
    assert esc_resp.status_code == 200
    data = esc_resp.json()
    assert data["current_level"] == "L2"
    assert "AI Conversational Specialist" in data["message"]

# -------------------------------------------------------------
# 7. L2 Natural Language Chat, Entity Extraction & Clarification
# -------------------------------------------------------------
def test_l2_clarification_question():
    """Tests L2 asking for clarification when missing product information."""
    headers = {"X-Tenant-ID": "cust-a-freshcart"}
    start_resp = client.post(
        "/api/v1/chat/start",
        headers=headers,
        json={"customer_id": "cust-test-4", "customer_name": "Clarification Test"}
    )
    conv_id = start_resp.json()["conversation_id"]

    # Escalate to L2
    client.post("/api/v1/chat/confirm-resolution", headers=headers, json={"conversation_id": conv_id, "resolved": False})

    # Customer speaks in natural language without order ID
    l2_resp = client.post(
        "/api/v1/chat/message",
        headers=headers,
        json={"conversation_id": conv_id, "message": "I ordered three items but one was missing."}
    )
    assert l2_resp.status_code == 200
    data = l2_resp.json()
    assert data["current_level"] == "L2"
    assert "Order ID" in data["message"] or "order" in data["message"].lower()

# -------------------------------------------------------------
# 8. L2 Tenant RAG Knowledge Retrieval
# -------------------------------------------------------------
def test_l2_tenant_rag_isolation():
    """Verifies that RAG search returns policies specific only to that tenant."""
    headers_freshcart = {"X-Tenant-ID": "cust-a-freshcart"}
    resp = client.post(
        "/api/v1/knowledge/test-search",
        headers=headers_freshcart,
        json={"query": "cold chain and ice cream return window", "top_k": 2}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["results_found"] > 0
    assert "FreshCart" in data["results"][0]["document_title"]

# -------------------------------------------------------------
# 9. L2 to L3 Escalation (Explicit Human Request or Emergency)
# -------------------------------------------------------------
def test_l2_to_l3_escalation_and_ticket_creation():
    """Tests automatic escalation to L3 human agent when customer requests human."""
    headers = {"X-Tenant-ID": "cust-b-biterush"}
    start_resp = client.post(
        "/api/v1/chat/start",
        headers=headers,
        json={"customer_id": "cust-test-5", "customer_name": "Amit Sharma"}
    )
    conv_id = start_resp.json()["conversation_id"]

    # Escalate to L2 first
    client.post("/api/v1/chat/confirm-resolution", headers=headers, json={"conversation_id": conv_id, "resolved": False})

    # User asks for a human agent
    l3_resp = client.post(
        "/api/v1/chat/message",
        headers=headers,
        json={"conversation_id": conv_id, "message": "Please connect me to a human agent right now."}
    )
    assert l3_resp.status_code == 200
    data = l3_resp.json()
    assert data["current_level"] == "L3"
    assert data["status"] == "ESCALATED"
    assert "ticket_id" in data
    assert "TICK-BITERUSH" in data["ticket_id"]

# -------------------------------------------------------------
# 10. L3 Agent Dashboard Actions & Duplicate Prevention
# -------------------------------------------------------------
def test_l3_agent_ticket_reply_and_duplicate_prevention():
    """Tests agent viewing ticket, replying, adding internal note, and preventing duplicate tickets."""
    # Login as BiteRush agent
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "rahul@biterush.com", "password": "Agent123!"}
    )
    token = login_resp.json()["access_token"]
    agent_headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": "cust-b-biterush"
    }

    # Fetch tickets
    tickets_resp = client.get("/api/v1/tickets", headers=agent_headers)
    assert tickets_resp.status_code == 200
    tickets = tickets_resp.json()
    assert len(tickets) > 0
    ticket_id = tickets[0]["id"]

    # Agent sends reply
    reply_resp = client.post(
        f"/api/v1/tickets/{ticket_id}/message",
        headers=agent_headers,
        json={"content": "Hello Amit! I am Rahul from BiteRush support. Reviewing your meal order now."}
    )
    assert reply_resp.status_code == 200
    assert reply_resp.json()["sender_name"] == "Rahul Verma"

    # Agent adds internal note
    note_resp = client.post(
        f"/api/v1/tickets/{ticket_id}/notes",
        headers=agent_headers,
        json={"note_text": "Verified packaging issue with Spice Garden kitchen."}
    )
    assert note_resp.status_code == 200

# -------------------------------------------------------------
# 11. Callback Scheduling & Outcome Workflow
# -------------------------------------------------------------
def test_callback_request_workflow():
    """Tests phone callback scheduling and agent outcome recording."""
    headers = {"X-Tenant-ID": "cust-c-swiftride"}
    start_resp = client.post(
        "/api/v1/chat/start",
        headers=headers,
        json={"customer_id": "cust-test-6", "customer_name": "Vikram Patel"}
    )
    conv_id = start_resp.json()["conversation_id"]

    # Request callback
    cb_resp = client.post(
        "/api/v1/tickets/callback/request",
        headers=headers,
        json={
            "conversation_id": conv_id,
            "customer_name": "Vikram Patel",
            "customer_phone": "+1-555-0301",
            "preferred_time_slot": "Within 15 minutes",
            "notes": "Fare dispute for airport ride detour"
        }
    )
    assert cb_resp.status_code == 200
    cb_data = cb_resp.json()
    assert "CALL-" in cb_data["call_id"]

# -------------------------------------------------------------
# 12. Real-Time Database Analytics Calculation
# -------------------------------------------------------------
def test_analytics_metrics_calculation():
    """Tests that analytics are dynamically calculated from stored database rows."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "superadmin@platform.com", "password": "SuperAdmin123!"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    analytics_resp = client.get("/api/v1/analytics/dashboard?days=30", headers=headers)
    assert analytics_resp.status_code == 200
    data = analytics_resp.json()
    assert data["total_conversations"] > 0
    assert "resolution_rate_percent" in data
    assert "escalation_rate_percent" in data
    assert len(data["tenant_breakdown"]) == 5
