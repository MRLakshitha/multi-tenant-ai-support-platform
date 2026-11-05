from fastapi import APIRouter

from app.api.v1 import (
    auth,
    tenants,
    chat,
    l3_tickets,
    knowledge,
    analytics,
    websocket,
    image_to_code,
)

api_router = APIRouter()

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication & RBAC"],
)

api_router.include_router(
    tenants.router,
    prefix="/tenants",
    tags=["Multi-Tenant Management"],
)

api_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["Support Chat (L1 & L2)"],
)

api_router.include_router(
    l3_tickets.router,
    prefix="/tickets",
    tags=["Human Support & Callbacks (L3)"],
)

api_router.include_router(
    knowledge.router,
    prefix="/knowledge",
    tags=["RAG Knowledge Base"],
)

api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["Real-Time Analytics"],
)

api_router.include_router(
    websocket.router,
    tags=["WebSockets"],
)

# New module: Image to Code Studio
api_router.include_router(
    image_to_code.router,
    prefix="/image-to-code",
    tags=["Image to Code Studio"],
)