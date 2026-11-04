# Multi-Tenant AI Support Platform

An AI-powered customer support platform built using Python, FastAPI, SQLite and Retrieval-Augmented Generation (RAG). The platform supports multiple organisations, customer conversations, automated issue resolution, ticket escalation and support analytics.

## 1. Project Overview

The Multi-Tenant AI Support Platform enables multiple organisations to manage their customer support operations independently through a single application.

Each organisation has its own customer support workflows, knowledge base, tickets and analytics.

The platform supports three levels of customer support:

- **L1 – Automated Support:** AI-assisted responses and predefined support workflows.
- **L2 – Advanced Support:** Additional troubleshooting and knowledge-base assistance.
- **L3 – Human Support:** Escalation to human agents through support tickets.

## 2. Supported Organisations

| Organisation | Industry |
|---|---|
| FreshCart Quick | Grocery and retail |
| BiteRush | Food delivery |
| SwiftRide | Transportation |
| StyleNova | Fashion and apparel |
| VoltExpress | Courier and logistics |

## 3. Technology Stack

**Backend**
- Python
- FastAPI
- SQLAlchemy
- SQLite
- Pydantic
- JWT authentication

**Frontend**
- HTML5
- CSS3
- JavaScript

**AI and Knowledge Retrieval**
- Retrieval-Augmented Generation (RAG)
- Knowledge-base document retrieval
- Tenant-specific knowledge isolation

**Testing and API Documentation**
- Pytest
- FastAPI Swagger UI

## 4. Key Features

### Multi-Tenant Architecture
- Supports five independent organisations.
- Maintains tenant-specific customer support information.
- Enforces tenant-level data isolation.
- Allows Super Admin to manage multiple tenants.

### Authentication and Authorization
- JWT-based authentication.
- Role-based access control.
- Super Admin, Tenant Admin and Support Agent roles.
- Protected API endpoints.

### AI Customer Support
- Customer conversation management.
- Automated issue categorisation.
- Order and reference ID validation.
- Knowledge-base retrieval.
- Customer issue resolution and escalation.

### L1/L2/L3 Escalation
- L1 automated customer assistance.
- L2 advanced troubleshooting.
- L3 escalation to human support.
- Automatic support ticket creation for escalated issues.

### Ticket Management
- Ticket creation and retrieval.
- Priority and status management.
- Agent replies.
- Internal notes.
- Resolution tracking.

### Analytics Dashboard
- Total conversations.
- L1, L2 and L3 resolution metrics.
- Resolution and escalation rates.
- Open, pending and resolved tickets.
- Customer satisfaction metrics.
- Tenant-level analytics.

## 5. Project Structure

```text
New folder (2)/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── services/
│   │
│   ├── tests/
│   ├── main.py
│   └── .venv/
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
│
├── support_platform.db
├── .env
└── README.md
```

## 6. Installation and Setup

### Prerequisites
- Python 3.12
- pip
- VS Code (recommended)

### Step 1: Open the project directory

```powershell
cd "C:\Users\MyPC\OneDrive\Documents\Desktop\New folder (2)"
```

### Step 2: Activate the virtual environment

```powershell
.\backend\.venv\Scripts\Activate.ps1
```

### Step 3: Start the backend

```powershell
python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

### Step 4: Open the application

Frontend:

http://127.0.0.1:8000/

Swagger API documentation:

http://127.0.0.1:8000/docs

Health check:

http://127.0.0.1:8000/health

## 7. API Modules

| Module | Endpoint |
|---|---|
| Authentication | `/api/v1/auth` |
| Tenant Management | `/api/v1/tenants` |
| Customer Chat | `/api/v1/chat` |
| Ticket Management | `/api/v1/tickets` |
| Knowledge Base | `/api/v1/knowledge` |
| Analytics | `/api/v1/analytics` |

Most tenant-specific endpoints require the `X-Tenant-ID` header. Protected endpoints also require a valid JWT access token.

## 8. Testing

Run the selected regression tests from the project root:

```powershell
python -m pytest .\backend\tests\test_all_features.py -v -k "all_five_tenants_present or cross_tenant_isolation_enforced or auth_login_and_me or l2_tenant_rag_isolation or analytics_metrics_calculation"
```

Run Python compilation checks:

```powershell
python -m compileall -q .\backend
```

## 9. Demo Scenarios

Use the frontend to demonstrate:

1. FreshCart – Damaged grocery products and returns.
2. BiteRush – Food delivery delays and missing items.
3. SwiftRide – Incorrect ride fares.
4. StyleNova – Wrong product size and exchanges.
5. VoltExpress – Delayed shipments and tracking complaints.

Demonstrate customer conversations, knowledge retrieval, escalation, ticket management and analytics.

Sample reference IDs used for demonstrations may not correspond to existing database orders.

## 10. Security Considerations

- Store secret keys and sensitive configuration in environment variables.
- Never commit `.env` files or JWT tokens to source control.
- Use strong, randomly generated JWT signing secrets.
- Enforce tenant isolation on all tenant-specific operations.
- Use HTTPS and production-grade configuration when deploying.

## 11. Future Enhancements

- Real-time agent communication.
- Improved AI response generation.
- Email and notification integration.
- Advanced customer sentiment analysis.
- Cloud deployment.
- Production-grade monitoring and logging.

## 12. Project Summary

The Multi-Tenant AI Support Platform demonstrates backend API development, multi-tenant architecture, authentication, authorization, AI-powered customer support, knowledge retrieval, escalation workflows, ticket management and analytics.

It provides a foundation for organisations to manage customer support operations through a unified platform while maintaining tenant-level data separation.