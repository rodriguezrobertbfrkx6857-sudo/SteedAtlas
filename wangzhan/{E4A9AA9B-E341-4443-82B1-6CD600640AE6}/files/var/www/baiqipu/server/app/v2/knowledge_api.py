import html
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import Field
from sqlalchemy import select

from app.database import get_db
from app.services.auth import get_current_admin_user, get_current_staff_user, get_current_user, get_optional_user

from .contracts import PassageInput, SourceInput, Strict
from .domain import create, digest, emit, owned, pack, revise
from .knowledge import AnswerService, KnowledgeRepository
from .models import Entity
from .research import ResearchAgent, ResearchPolicy

router = APIRouter(prefix="/api/v2", tags=["Evidence core"])


class Message(Strict):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class AnswerRequest(Strict):
    messages: list[Message] = Field(min_length=1, max_length=12)
    scope: Literal["history", "all", "literature"] = "all"


class CitationCheck(Strict):
    citations: list[dict] = Field(max_length=30)


class SourceEdit(Strict):
    expected_version: int = Field(ge=1)
    source: SourceInput


class PassageEdit(Strict):
    expected_version: int = Field(ge=1)
    passage: PassageInput


class EntityInput(Strict):
    name: str = Field(min_length=1, max_length=160)
    entity_type: Literal["Horse", "Person", "Event", "Work", "Location"]
    aliases: list[str] = Field(default_factory=list, max_length=30)


class EntityEdit(Strict):
    expected_version: int = Field(ge=1)
    entity: EntityInput


class ResearchRequest(Strict):
    query: str = Field(min_length=1, max_length=500)
    mode: Literal["RULE_BASED", "LIVE_LLM", "JEV"] = "RULE_BASED"
    strategy: Literal["single", "fixed", "adaptive"] = "adaptive"
    max_calls: int = Field(default=8, ge=2, le=10)
    max_rounds: int = Field(default=3, ge=1, le=3)
    acquire_sources: bool = False


class Review(Strict):
    expected_version: int = Field(ge=1)
    decision: Literal["ACCEPT", "REJECT"]
    note: str = Field(min_length=1, max_length=1000)


@router.post("/answers")
def answer(req: AnswerRequest, db=Depends(get_db), user=Depends(get_optional_user)):
    from .knowledge import record_answer

    result = AnswerService(db, user).answer([m.model_dump() for m in req.messages], req.scope)
    return record_answer(db, user, result)


@router.get("/answers/{identity}")
def answer_audit(identity: str, db=Depends(get_db), user=Depends(get_current_user)):
    e = owned(db, identity, user.id, "knowledge_answer")
    repo = KnowledgeRepository(db)
    citations = e.data.get("citations", [])
    stale = any(not repo.validate(c) for c in citations) or e.data["corpus_snapshot_id"] != repo.snapshot
    if stale:
        return {
            "id": e.id,
            "version": e.version,
            "stale": True,
            "provenance_digest": e.data["provenance_digest"],
            "valid_citations": [repo.validate(c) for c in citations],
            "message": "知识快照已变化，历史记录保留；请重新检索以查看当前允许的内容。",
        }
    if any(not repo.public(repo.rows.get(c["source_id"])) for c in citations):
        return {"id": e.id, "stale": True, "message": "来源权限已变更，历史答案内容已隐藏。"}
    return {**pack(e), "stale": stale, "valid_citations": [repo.validate(c) for c in citations]}


@router.get("/knowledge/shadow-compare")
def shadow(q: str = Query(min_length=1, max_length=200), db=Depends(get_db)):
    from app.services.ai_engine import _cosine_sim, _embed_text

    from .knowledge import EvidenceSearch

    repo = KnowledgeRepository(db)
    query = _embed_text(q)
    legacy = sorted(
        [{"id": d["id"], "score": _cosine_sim(query, _embed_text(d["text"]))} for d in repo.legacy_editorial],
        key=lambda x: x["score"],
        reverse=True,
    )[:5]
    unified = EvidenceSearch(repo).search(q, "all", 5)
    return {
        "corpus_snapshot_id": repo.snapshot,
        "legacy": legacy,
        "unified": unified,
        "classification": "EDITORIAL_VS_REVIEWED_EVIDENCE",
        "mode": "READ_ONLY_NO_LLM",
        "query_digest": digest(q),
        "logged_query_text": False,
    }


@router.get("/knowledge/status")
def status(db=Depends(get_db)):
    return KnowledgeRepository(db).coverage()


@router.get("/knowledge/identity-candidates")
def identity_candidates(horse_id: str = Query(max_length=64), db=Depends(get_db)):
    rows = db.scalars(select(Entity).where(Entity.kind == "entity_candidate")).all()
    return {
        "status": "UNRESOLVED_METADATA_NOT_HISTORICAL_EVIDENCE",
        "items": [
            pack(e) for e in rows if e.data.get("catalogue_id") == horse_id and e.data.get("visibility") == "PUBLIC"
        ],
    }


@router.get("/knowledge/creative")
def creative(q: str = Query(min_length=1, max_length=200), db=Depends(get_db)):
    return KnowledgeRepository(db).creative_search(q)


@router.get("/knowledge/entities")
def entities(q: str = Query(min_length=1, max_length=200), db=Depends(get_db)):
    return KnowledgeRepository(db).entities(q)


@router.post("/admin/knowledge/entities")
def new_entity(req: EntityInput, db=Depends(get_db), user=Depends(get_current_staff_user)):
    e = create(db, "knowledge_entity", user.id, req.model_dump())
    db.commit()
    return pack(e)


@router.patch("/admin/knowledge/entities/{identity}")
def edit_entity(identity: str, req: EntityEdit, db=Depends(get_db), user=Depends(get_current_staff_user)):
    e = db.get(Entity, identity)
    if not e or e.kind != "knowledge_entity":
        raise HTTPException(404, "Entity not found")
    revise(db, e, req.expected_version, req.entity.model_dump(), user.id)
    db.commit()
    return pack(e)


@router.post("/evidence/validate")
def validate(req: CitationCheck, db=Depends(get_db)):
    repo = KnowledgeRepository(db)
    checks = [repo.validate(c) for c in req.citations]
    return {"valid": checks, "stale": not all(checks), "corpus_snapshot_id": repo.snapshot}


@router.get("/evidence/{reference}", response_class=HTMLResponse)
def evidence(reference: str, db=Depends(get_db)):
    try:
        identity, version = reference.rsplit("@", 1)
        version = int(version)
    except ValueError:
        raise HTTPException(404, "Evidence not found") from None
    repo = KnowledgeRepository(db)
    d = repo.revision(identity, version, "claim")
    p = repo.revision(d["passage_id"], d["passage_version"], "passage")
    s = repo.revision(d["source_id"], d.get("source_version", 1), "source")
    span = d.get("span") or [0, len(p["content"])]
    esc = html.escape
    current = repo.rows[identity]
    stale = current.version != version or not repo.citation(current)
    machine = d.get("presentation_track") == "AUTO_VERIFIED_SOURCE"
    label = (
        "STALE / 引用失效，不能作为有效证据"
        if stale
        else "MACHINE_VERIFIED · 机器核对原文，未人工审核；不等于史实或语义支持已验证"
        if machine
        else "已审核文献摘录"
    )
    return (
        '<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>百骑谱 · 原文证据</title><body style="background:#0b0b0b;color:#dbc58f;font:18px/1.8 serif;max-width:760px;margin:4vh auto;padding:24px">'
        + f"<h1>{esc(s.get('title', '来源'))}</h1><p>{label}</p>"
        + f"<p>{esc(s.get('kind', 'UNKNOWN'))} · {esc(s.get('edition', '版本待核'))}</p><p>{esc(p.get('locator', ''))}</p>"
        + f"<blockquote>{esc(p['content'][: span[0]])}<mark>{esc(p['content'][span[0] : span[1]])}</mark>{esc(p['content'][span[1] :])}</blockquote>"
        + f"<p>Claim {esc(reference)} · Passage {esc(d['passage_id'])}@{d['passage_version']} · Source @{d.get('source_version', 1)}</p>"
        + f"<p>{esc(s.get('attribution', ''))}</p><p>{esc(s.get('changes', ''))}</p>"
        + (
            f'<p><a style="color:#e0c277" rel="noreferrer" href="{esc(s["license_url"], quote=True)}">{esc(s.get("license", "许可"))}</a></p>'
            if s.get("license_url", "").startswith("https://creativecommons.org/licenses/")
            else ""
        )
        + (
            f'<p><a style="color:#e0c277" rel="noreferrer" href="{esc(s["url"], quote=True)}">查看文献页面</a></p>'
            if s.get("url", "").startswith("https://")
            else ""
        )
        + "</body></html>"
    )


@router.get("/passage-evidence/{reference}", response_class=HTMLResponse)
def raw_passage(reference: str, db=Depends(get_db)):
    try:
        identity, version = reference.rsplit("@", 1)
        version = int(version)
    except ValueError:
        raise HTTPException(404, "Passage not found") from None
    repo = KnowledgeRepository(db)
    p = repo.revision(identity, version, "passage")
    s = repo.rows[p["source_id"]]
    esc = html.escape
    return (
        '<!doctype html><html lang="zh"><meta charset="utf-8"><title>百骑谱 · 待核原文</title><body style="background:#0b0b0b;color:#dbc58f;max-width:760px;margin:4vh auto;padding:24px;line-height:1.8">'
        + f"<h1>{esc(s.data.get('title', '来源'))}</h1><p>未审核段落，不代表事实支持关系。版本 {esc(reference)}</p><p>{esc(p.get('locator', ''))}</p><blockquote>{esc(p['content'])}</blockquote></body></html>"
    )


def invalidate_dependents(db, identity, actor):
    from .api import _invalidate_claim

    for c in db.scalars(select(Entity).where(Entity.kind == "claim")).all():
        if identity in (c.data.get("source_id"), c.data.get("passage_id")):
            _invalidate_claim(db, c.id, actor)
    emit(db, identity, actor, "EVIDENCE_INDEX_INVALIDATED")


@router.patch("/admin/sources/{identity}")
def edit_source(identity: str, req: SourceEdit, db=Depends(get_db), user=Depends(get_current_staff_user)):
    s = db.get(Entity, identity)
    if not s or s.kind != "source":
        raise HTTPException(404, "Source not found")
    revise(db, s, req.expected_version, req.source.model_dump(), user.id)
    invalidate_dependents(db, identity, user.id)
    db.commit()
    return pack(s)


@router.patch("/admin/passages/{identity}")
def edit_passage(identity: str, req: PassageEdit, db=Depends(get_db), user=Depends(get_current_staff_user)):
    p = db.get(Entity, identity)
    if not p or p.kind != "passage":
        raise HTTPException(404, "Passage not found")
    if req.passage.source_id != p.data["source_id"]:
        raise HTTPException(422, "SOURCE_ID_IMMUTABLE")
    d = req.passage.model_dump()
    revise(
        db, p, req.expected_version, {**d, "text_hash": digest(d["content"]), "span": [0, len(d["content"])]}, user.id
    )
    invalidate_dependents(db, identity, user.id)
    db.commit()
    return pack(p)


@router.post("/admin/sources/{identity}/retire")
def retire_source(identity: str, db=Depends(get_db), user=Depends(get_current_admin_user)):
    s = db.get(Entity, identity)
    if not s or s.kind != "source":
        raise HTTPException(404, "Source not found")
    revise(db, s, s.version, {**s.data, "review_state": "RETIRED"}, user.id)
    invalidate_dependents(db, identity, user.id)
    db.commit()
    return pack(s)


@router.post("/research/runs")
def research(req: ResearchRequest, db=Depends(get_db), user=Depends(get_current_user)):
    if req.mode != "RULE_BASED":
        raise HTTPException(409, "BLOCKED: external provider requires explicit authorization and validated adapter")
    if req.acquire_sources and os.environ.get("SOURCE_AUTODISCOVERY_ENABLED") != "1":
        raise HTTPException(409, "SOURCE_ACQUISITION_NOT_ENABLED_ON_THIS_INSTANCE")
    agent = ResearchAgent(
        db,
        ResearchPolicy(
            max_calls=req.max_calls,
            max_rounds=req.max_rounds,
            allow_acquisition=req.acquire_sources,
            max_seconds=45 if req.acquire_sources else 10,
        ),
        owner=user.id,
    )
    from contextlib import nullcontext
    from pathlib import Path

    from .acquisition_limits import acquisition_slot

    slot = (
        acquisition_slot(Path(os.environ["STEEDATLAS_ROOT"]) / "runtime/acquisition-limits.db", user.id)
        if req.acquire_sources
        else nullcontext()
    )
    try:
        with slot:
            data = agent.run(req.query, req.strategy)
    except Exception as exc:
        db.rollback()
        failed = create(
            db,
            "research_proposal",
            user.id,
            {
                "mode": "RULE_BASED",
                "state": "FAILED",
                "trace": agent.trace,
                "error_type": type(exc).__name__,
                "tokens": 0,
                "cost": 0,
                "reason": str(exc.detail) if isinstance(exc, HTTPException) else "RESEARCH_EXECUTION_FAILED",
            },
        )
        db.commit()
        raise HTTPException(
            exc.status_code if isinstance(exc, HTTPException) else 503,
            {"reason": failed.data["reason"], "trace_id": failed.id},
        ) from exc
    e = create(db, "research_proposal", user.id, data)
    db.commit()
    return pack(e)


@router.get("/research/runs/{identity}")
def research_trace(identity: str, db=Depends(get_db), user=Depends(get_current_user)):
    e = owned(db, identity, user.id, "research_proposal")
    # Stored evidence must not leak a source subsequently made private.
    repo = KnowledgeRepository(db)
    if e.data["corpus_snapshot_id"] != repo.snapshot or any(
        not repo.validate(h["citation"]) for h in e.data.get("evidence", [])
    ):
        return {"id": e.id, "version": e.version, "stale": True, "data": {"review_state": e.data["review_state"]}}
    return pack(e)


@router.post("/research/runs/{identity}/review")
def review_research(identity: str, req: Review, db=Depends(get_db), user=Depends(get_current_user)):
    e = owned(db, identity, user.id, "research_proposal")
    if e.data["review_state"] != "PENDING" or e.data["corpus_snapshot_id"] != KnowledgeRepository(db).snapshot:
        raise HTTPException(409, "STALE_OR_REVIEWED_PROPOSAL")
    revise(db, e, req.expected_version, {**e.data, "review_state": req.decision, "review_note": req.note}, user.id)
    emit(db, e.id, user.id, "RESEARCH_HUMAN_REVIEW", {"decision": req.decision})
    # Accept records a finding only; historical assertions still require staff draft + admin review.
    db.commit()
    return pack(e)


@router.get("/snapshot-evidence/{identity}", response_class=HTMLResponse)
def snapshot_evidence(identity: str, db=Depends(get_db)):
    repo = KnowledgeRepository(db, snapshot_only=True)
    claim = repo.rows.get(identity)
    c = repo.citation(claim) if claim and claim.kind == "claim" else None
    if not c or c["verification"] != "MACHINE_VERIFIED_SNAPSHOT":
        raise HTTPException(404, "SNAPSHOT_UNAVAILABLE_OR_RESTRICTED")
    esc = html.escape
    return (
        '<!doctype html><html lang="zh"><meta charset="utf-8"><title>百骑谱 · 保存快照</title>'
        '<body style="background:#0b0b0b;color:#dbc58f;max-width:760px;margin:4vh auto;padding:24px;line-height:1.8">'
        "<h1>保存快照 · 非实时 · 未人工审核</h1><p>此页仅核对保存的版本和原文，不表示来源当前可用，也不证明史实。</p>"
        + f"<p>最后成功观察：{esc(str(c['source_observation'].get('checked_at')))} · {esc(str(c['source_observation'].get('status')))}</p>"
        + f"<h2>{esc(c['source_title'])}</h2><p>{esc(c['edition'])} · {esc(c['locator'])}</p>"
        + f"<blockquote>{esc(c['quote'])}</blockquote><p>{esc(c['attribution'])}</p>"
        + f'<a style="color:#e0c277" href="{esc(c["source_url"], quote=True)}">固定版本</a> · '
        + f'<a style="color:#e0c277" href="{esc(c["license_url"], quote=True)}">{esc(c["license"])}</a></body></html>'
    )
