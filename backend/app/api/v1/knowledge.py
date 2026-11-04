import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_verified_tenant, require_roles
from app.models.tenant import Tenant
from app.models.user import UserRole
from app.models.knowledge import KnowledgeDocument
from app.services.rag_engine import RAGEngine

router = APIRouter()

class DocumentCreateRequest(BaseModel):
    title: str
    doc_type: str = "POLICY"  # POLICY, FAQ, CANCELLATION, REFUND, SLA
    content: str

class TestSearchRequest(BaseModel):
    query: str
    top_k: int = 3

@router.get("")
def list_documents(
    tenant: Tenant = Depends(get_verified_tenant),
    db: Session = Depends(get_db)
):
    """Lists knowledge documents strictly scoped to this tenant."""
    docs = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.tenant_id == tenant.id,
        KnowledgeDocument.is_active == True
    ).order_by(KnowledgeDocument.created_at.desc()).all()
    
    return [
        {
            "id": d.id,
            "title": d.title,
            "doc_type": d.doc_type,
            "content_preview": d.content[:150] + "...",
            "content": d.content,
            "created_at": d.created_at.isoformat()
        }
        for d in docs
    ]

@router.post("", dependencies=[Depends(require_roles([UserRole.SUPER_ADMIN.value, UserRole.TENANT_ADMIN.value]))])
def create_document(
    req: DocumentCreateRequest,
    tenant: Tenant = Depends(get_verified_tenant),
    db: Session = Depends(get_db)
):
    """Uploads/adds a new knowledge document and partitions embeddings strictly for this tenant."""
    doc = KnowledgeDocument(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        title=req.title,
        doc_type=req.doc_type,
        content=req.content,
        is_active=True
    )
    db.add(doc)
    db.commit()

    # Index chunks with vector embeddings
    chunks = RAGEngine.index_document(
        db=db,
        tenant_id=tenant.id,
        document_id=doc.id,
        text=req.content
    )

    return {
        "status": "INDEXED",
        "document_id": doc.id,
        "title": doc.title,
        "chunks_indexed": len(chunks)
    }

@router.post("/test-search")
def test_rag_search(
    req: TestSearchRequest,
    tenant: Tenant = Depends(get_verified_tenant),
    db: Session = Depends(get_db)
):
    """Tests RAG semantic search within this tenant's partitioned knowledge base."""
    results = RAGEngine.search(
        db=db,
        tenant_id=tenant.id,
        query=req.query,
        top_k=req.top_k
    )
    return {
        "tenant_id": tenant.id,
        "query": req.query,
        "results_found": len(results),
        "results": results
    }
