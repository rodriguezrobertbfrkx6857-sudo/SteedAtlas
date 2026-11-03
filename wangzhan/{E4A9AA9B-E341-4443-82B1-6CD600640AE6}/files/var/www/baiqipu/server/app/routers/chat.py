import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.auth import get_optional_user
from app.services import ai_engine

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str
    content: str = Field(max_length=12000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=100)
    stream: bool = True


@router.get("/status")
def chat_status(db: Session = Depends(get_db)):
    from app.v2.knowledge import KnowledgeRepository
    r = KnowledgeRepository(db).coverage()
    return {**r, 'status': 'RETRIEVAL_ONLY', 'document_count': r['editorial_count'],
            'vector_count': 0, 'unique_horse_count': r['editorial_count'], 'top_k': 8,
            'sample_horses': ['赤兔', '乌骓', '的卢'], 'SOURCE_PRESENT': r['source_present'],
            'INDEX_READY': r['index_ready'], 'EVIDENCE_VERIFIED': r['evidence_verified'], 'LLM_AVAILABLE': False}


@router.post("")
async def chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    normalized_messages = [message.model_dump() for message in req.messages]
    reply = ai_engine.generate_chat_reply(normalized_messages, db, user=user)
    response_text = reply["message"]

    if req.stream:

        async def event_stream():
            for char in response_text:
                chunk = {"choices": [{"delta": {"content": char}}]}
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

            meta = {
                **{k: reply.get(k) for k in ('citations', 'evidence', 'summary', 'mode', 'review_status', 'corpus_snapshot_id', 'provenance_digest', 'answer_id')},
                "type": "meta",
                "sources": reply["sources"],
                "matched_horse": reply["matched_horse"],
                "recommended_product": reply["recommended_product"],
                "personality_match": reply.get("personality_match"),
                "recommendation_strategy": reply.get("recommendation_strategy"),
                "generation_mode": reply.get("generation_mode"),
                "model": reply.get("model"),
            }
            yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return reply
