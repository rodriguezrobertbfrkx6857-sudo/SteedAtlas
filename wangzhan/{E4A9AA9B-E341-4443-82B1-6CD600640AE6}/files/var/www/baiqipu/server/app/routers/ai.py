from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any

from app.services import ai_engine
from app.services.auth import get_current_admin_user
from app.database import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/ai", tags=["ai"])


class BuildIn(BaseModel):
    docs: List[Dict[str, Any]]
    out_path: str | None = None


class QueryIn(BaseModel):
    q: str
    top_k: int = 5


@router.post("/build")
def build(inp: BuildIn, user=Depends(get_current_admin_user)):
    if inp.out_path is not None:
        raise HTTPException(422, detail="User-selected output paths are prohibited")
    try:
        path = ai_engine.build_vectordb(inp.docs)
        return {"status": "ok", "index": "vectordb"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Index operation failed")


@router.post("/query")
def query(inp: QueryIn, db: Session = Depends(get_db)):
    try:
        from app.v2.knowledge import EvidenceSearch, KnowledgeRepository
        return EvidenceSearch(KnowledgeRepository(db)).search(inp.q[:2000], 'all', max(1, min(inp.top_k, 20)))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Index operation failed")
