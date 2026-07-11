from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from api.deps import get_current_user
from services.knowledge_base import KnowledgeBaseService

router = APIRouter(prefix="/api/kb", tags=["knowledge_base"])

class SearchRequest(BaseModel):
    query: str
    sources: List[str]
    searchMode: str = "semantic"

class UploadRequest(BaseModel):
    title: str
    source: str
    content: str
    citation: str

class UpdateRequest(BaseModel):
    docId: str
    content: str
    version: str

@router.get("/documents")
async def api_get_documents(user: dict = Depends(get_current_user)):
    return KnowledgeBaseService.get_documents()

@router.post("/search")
async def api_search(req: SearchRequest, user: dict = Depends(get_current_user)):
    return KnowledgeBaseService.search_kb(req.query, req.sources, req.searchMode)

@router.post("/upload")
async def api_upload(req: UploadRequest, user: dict = Depends(get_current_user)):
    if user["role"] not in ["Admin", "Operator", "Engineer", "Network Engineer", "Senior Engineer"]:
        raise HTTPException(status_code=403, detail="Permission Denied: Write actions restricted.")
    return KnowledgeBaseService.add_document(req.title, req.source, req.content, req.citation)

@router.post("/update")
async def api_update(req: UpdateRequest, user: dict = Depends(get_current_user)):
    if user["role"] not in ["Admin", "Operator"]:
        raise HTTPException(status_code=403, detail="Permission Denied: Document versioning updates restricted to Admins/Operators.")
    try:
        return KnowledgeBaseService.update_document_version(req.docId, req.content, req.version)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
