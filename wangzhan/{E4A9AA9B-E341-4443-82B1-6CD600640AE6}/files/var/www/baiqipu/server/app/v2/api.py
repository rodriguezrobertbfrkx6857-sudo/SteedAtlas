import copy
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.horses import _build_rag_library_items
from app.services.auth import get_current_admin_user, get_current_staff_user, get_current_user

from . import agent_providers, media
from .contracts import (
    ClaimInput,
    ClaimRevisionInput,
    CompileRequest,
    PassageInput,
    Project,
    ProposalRequest,
    ProposalReview,
    RenderRequest,
    SaveProject,
    SourceInput,
)
from .domain import (
    accept_patches,
    canonical_timeline,
    check_bible,
    create,
    digest,
    emit,
    impact,
    owned,
    pack,
    revise,
    rule_proposal,
)
from .knowledge import EvidenceSearch, KnowledgeRepository, bind_claim
from .models import Entity, Event, Job, Node, Revision
from .runtime import compile_plan

router = APIRouter(prefix="/api/v2", tags=["SteedAtlas V2"])
DB = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(get_current_user)]
Staff = Annotated[User, Depends(get_current_staff_user)]
Admin = Annotated[User, Depends(get_current_admin_user)]


@router.get("/capabilities")
def capabilities():
    return {
        "agent_modes": list(agent_providers.RUNTIME_MODES),
        "agent_provider_catalogue": agent_providers.catalogue(),
        "external_video": False,
        "publication": False,
        "renderer": "FFmpeg CPU",
        "legacy_commerce": "SANDBOX",
        "schema_version": 1,
    }


@router.get("/agent-providers")
def agent_provider_catalogue():
    """Truthful catalogue of every agent mode and what it actually does."""
    return agent_providers.catalogue()


@router.get("/horses")
def catalogue(db: DB, q: str = Query("", max_length=120), source_type: str = ""):
    rows = _build_rag_library_items(db)
    for alias, name in {"赤菟": "赤兔", "的颅": "的卢"}.items():
        q = q.replace(alias, name)
    rows = [r for r in rows if q.lower() in r.get("query_blob", "").lower() and source_type in r.get("source_type", "")]
    return {"items": [{k: v for k, v in r.items() if k != "query_blob"} for r in rows], "total": len(rows)}


@router.get("/horses/{horse_id}")
def detail(horse_id: str, db: DB):
    row = next((r for r in _build_rag_library_items(db) if r["id"] == horse_id), None)
    if not row:
        raise HTTPException(404, "Horse not found")
    claims = db.scalars(select(Entity).where(Entity.kind == "claim")).all()
    repo = KnowledgeRepository(db)
    return {**row, "claims": [pack(c) for c in claims if repo.public(c) and horse_id in repo.subjects(c)],
            "evidence": EvidenceSearch(repo).search(row['name'], 'all'), "knowledge_class": "EDITORIAL"}


@router.get("/search")
def search(db: DB, q: str = Query(min_length=1, max_length=120), mode: str = "history"):
    return EvidenceSearch(KnowledgeRepository(db)).search(q, mode, 5)


@router.get("/sources")
def sources(db: DB):
    repo = KnowledgeRepository(db)
    return [pack(e) for e in repo.rows.values() if e.kind in ('source', 'claim') and repo.public(e)]


@router.get("/sources/{source_id}/passages/{passage_id}")
def passage(source_id: str, passage_id: str, db: DB, version: int | None = None):
    repo = KnowledgeRepository(db)
    p = db.get(Entity, passage_id)
    source = db.get(Entity, source_id)
    if not repo.public(p) or p.kind != "passage" or p.data["source_id"] != source_id or not repo.public(source):
        raise HTTPException(404, "Passage not found")
    if version is not None and version != p.version:
        old = db.scalar(select(Revision).where(Revision.entity_id == p.id, Revision.version == version))
        if not old:
            raise HTTPException(404, "Passage version not found")
        return {"id": p.id, "version": version, "data": old.data, "source": pack(source)}
    return {**pack(p), "source": pack(source)}


@router.post("/admin/claims")
def new_claim(req: ClaimInput, db: DB, user: Staff):
    p = db.get(Entity, req.passage_id)
    if not p or p.kind != "passage" or p.version != req.passage_version or p.data["source_id"] != req.source_id:
        raise HTTPException(422, "INVALID_PASSAGE_REFERENCE")
    c = create(db, "claim", user.id, bind_claim(db, req.model_dump()))
    db.commit()
    return pack(c)


@router.post("/admin/sources", status_code=201)
def new_source(req: SourceInput, db: DB, user: Staff):
    e = create(db, "source", user.id, req.model_dump())
    db.commit()
    return pack(e)


@router.post("/admin/passages", status_code=201)
def new_passage(req: PassageInput, db: DB, user: Staff):
    source = db.get(Entity, req.source_id)
    if not source or source.kind != "source":
        raise HTTPException(422, "SOURCE_NOT_FOUND")
    e = create(
        db, "passage", user.id, {**req.model_dump(), "text_hash": digest(req.content), "span": [0, len(req.content)]}
    )
    db.commit()
    return pack(e)


@router.patch("/admin/claims/{identity}")
def correct_claim(identity: str, req: ClaimRevisionInput, db: DB, user: Staff):
    c = db.get(Entity, identity)
    p = db.get(Entity, req.claim.passage_id)
    if not c or c.kind != "claim":
        raise HTTPException(404, "Claim not found")
    if (
        not p
        or p.kind != "passage"
        or p.version != req.claim.passage_version
        or p.data["source_id"] != req.claim.source_id
    ):
        raise HTTPException(422, "INVALID_PASSAGE_REFERENCE")
    new = {**bind_claim(db, req.claim.model_dump()), "horse_name": c.data.get("horse_name", "")}
    revise(db, c, req.expected_version, new, user.id)
    _invalidate_claim(db, c.id, user.id)
    db.commit()
    return pack(c)


@router.post("/admin/claims/{identity}/approve")
def approve_claim(identity: str, db: DB, user: Admin):
    c = db.get(Entity, identity)
    if not c or c.kind != "claim":
        raise HTTPException(404, "Claim not found")
    if not KnowledgeRepository(db).citation(c, require_approved=False):
        raise HTTPException(422, 'INVALID_OR_UNLICENSED_EVIDENCE: bind current source/passage revisions and exact span')
    new = {**c.data, "review_state": "APPROVED", "reviewer_id": user.id}
    revise(db, c, c.version, new, user.id)
    _invalidate_claim(db, c.id, user.id)
    db.commit()
    return pack(c)


def _invalidate_claim(db, identity, actor):
    for p in db.scalars(select(Entity).where(Entity.kind == "project")):
        if (any(any(r.startswith(identity + "@") for r in s["claim_refs"]) for s in p.data["scenes"]) or
                any(h.get('id') == identity for h in p.data.get('knowledge_bundle', {}).get('results', []))):
            revise(db, p, p.version, {**p.data, "review_state": "NEEDS_REVIEW"}, actor)
    for j in db.scalars(select(Job)):
        if (any(any(r.startswith(identity + "@") for r in s["claim_refs"]) for s in j.snapshot["scenes"]) or
                any(h.get('id') == identity for h in j.snapshot.get('knowledge_bundle', {}).get('results', []))):
            j.status = "NEEDS_REVIEW"
            emit(db, j.id, actor, "CLAIM_CHANGED", {"claim_id": identity})


@router.post("/admin/claims/{identity}/retire")
def retire_claim(identity: str, db: DB, user: Admin):
    c = db.get(Entity, identity)
    if not c or c.kind != "claim":
        raise HTTPException(404, "Claim not found")
    revise(db, c, c.version, {**c.data, "review_state": "RETIRED"}, user.id)
    _invalidate_claim(db, c.id, user.id)
    db.commit()
    return pack(c)


@router.post("/projects", status_code=201)
def create_project(req: Project, db: DB, user: Actor):
    data = req.model_dump()
    data["review_state"] = "DRAFT"
    data['knowledge_bundle'] = EvidenceSearch(KnowledgeRepository(db)).search(req.horse_id, 'all')
    p = create(db, "project", user.id, data)
    db.commit()
    return {**pack(p), "timeline": canonical_timeline(p.data)}


@router.get("/projects")
def projects(db: DB, user: Actor):
    return [pack(p) for p in db.scalars(select(Entity).where(Entity.kind == "project", Entity.owner == user.id))]


@router.get("/projects/{identity}")
def get_project(identity: str, db: DB, user: Actor):
    p = owned(db, identity, user.id, "project")
    latest = db.scalar(
        select(Job).where(Job.project_id == identity, Job.owner == user.id).order_by(Job.created_at.desc())
    )
    return {
        **pack(p),
        "timeline": canonical_timeline(p.data),
        "findings": check_bible(p.data),
        "latest_job": latest.id if latest else None,
    }


@router.get("/projects/{identity}/revisions")
def revisions(identity: str, db: DB, user: Actor):
    owned(db, identity, user.id, "project")
    return [
        {"version": r.version, "data": r.data}
        for r in db.scalars(select(Revision).where(Revision.entity_id == identity).order_by(Revision.version))
    ]


@router.patch("/projects/{identity}/revisions")
def save_project(identity: str, req: SaveProject, db: DB, user: Actor):
    p = owned(db, identity, user.id, "project")
    new = req.project.model_dump()
    new["review_state"] = "DRAFT"
    new['knowledge_bundle'] = EvidenceSearch(KnowledgeRepository(db)).search(req.project.horse_id, 'all')
    changes = impact(p.data, new)
    revise(db, p, req.expected_version, new, user.id)
    db.commit()
    return {**pack(p), "impact": changes, "timeline": canonical_timeline(p.data)}


@router.post("/projects/{identity}/approve")
def approve_project(identity: str, req: RenderRequest, db: DB, user: Actor):
    p = owned(db, identity, user.id, "project")
    if check_bible(p.data):
        raise HTTPException(422, "SCENE_REVIEW_FINDINGS")
    from .runtime import claim_guard

    try:
        claim_guard(db, p.data)
    except ValueError as e:
        raise HTTPException(409, str(e)) from None
    revise(db, p, req.expected_version, {**p.data, "review_state": "APPROVED"}, user.id)
    emit(db, p.id, user.id, "HUMAN_APPROVED", {"version": p.version})
    db.commit()
    return pack(p)


@router.post("/projects/{identity}/agent-runs")
def agent_run(identity: str, req: ProposalRequest, db: DB, user: Actor):
    p = owned(db, identity, user.id, "project")
    if p.version != req.expected_version:
        raise HTTPException(409, "VERSION_CONFLICT")
    if req.mode not in agent_providers.RUNTIME_MODES:
        provider = agent_providers.describe(req.mode)
        reason = agent_providers.BLOCKED_REASON if req.mode == "LIVE_LLM" else "UNAVAILABLE_MODE"
        raise HTTPException(409, f"{reason}: {provider['description']}")
    prior = [
        x
        for x in db.scalars(select(Entity).where(Entity.kind == "proposal", Entity.owner == user.id))
        if x.data["project_id"] == identity and x.data["base_version"] == p.version
    ]
    if len(prior) >= 3:
        raise HTTPException(429, "REPAIR_BUDGET_EXHAUSTED: human revision required")
    data = (
        rule_proposal(p.data, req.intent)
        if req.mode == "RULE_BASED"
        else {"mode": "MANUAL", "roles": [], "patches": [], "tool_calls": []}
    )
    if req.mode == "RULE_BASED":
        from .runtime import claim_guard

        try:
            claim_guard(db, p.data)
            data["tool_results"].append({"tool": "validate_citations", "result": "VALID"})
        except ValueError as exc:
            data["findings"].append({"code": str(exc)})
            data["tool_results"].append({"tool": "validate_citations", "result": "NEEDS_REVIEW"})
    proposal = create(
        db, "proposal", user.id, {**data, "project_id": identity, "base_version": p.version, "max_turns": req.max_turns}
    )
    db.commit()
    return pack(proposal)


@router.get("/projects/{identity}/agent-runs")
def traces(identity: str, db: DB, user: Actor):
    owned(db, identity, user.id, "project")
    return [
        pack(x)
        for x in db.scalars(select(Entity).where(Entity.kind == "proposal", Entity.owner == user.id))
        if x.data["project_id"] == identity
    ]


@router.post("/agent-proposals/{identity}/review")
def review_proposal(identity: str, req: ProposalReview, db: DB, user: Actor):
    proposal = owned(db, identity, user.id, "proposal")
    if proposal.data.get("review_state") != "PENDING":
        raise HTTPException(409, "PROPOSAL_ALREADY_REVIEWED")
    p = owned(db, proposal.data["project_id"], user.id, "project")
    if req.expected_version != p.version or proposal.data["base_version"] != p.version:
        raise HTTPException(409, "STALE_PROPOSAL")
    if req.decision == "ACCEPT":
        revise(db, p, p.version, accept_patches(p.data, proposal.data["patches"]), user.id)
    revise(
        db, proposal, proposal.version, {**proposal.data, "review_state": req.decision, "reviewer": user.id}, user.id
    )
    db.commit()
    return pack(p)


@router.post("/projects/{identity}/assets", status_code=201)
async def upload_asset(identity: str, db: DB, user: Actor, file: UploadFile = File(...), rights: str = Form("UNKNOWN")):
    owned(db, identity, user.id, "project")
    if rights not in {"OWNED", "LICENSED", "PUBLIC_DOMAIN", "UNKNOWN"}:
        raise HTTPException(422, "INVALID_RIGHTS")
    temp = media.STORE / (uuid.uuid4().hex + ".upload")
    total = 0
    try:
        with temp.open("wb") as f:
            while block := await file.read(1024 * 1024):
                total += len(block)
                if total > 30 * 1024 * 1024:
                    raise HTTPException(413, "UPLOAD_TOO_LARGE")
                f.write(block)
        if not total:
            raise ValueError("EMPTY_UPLOAD")
        metadata = media.validate_upload(temp)
        data = media.artifact(
            temp,
            **metadata,
            rights_status=rights,
            project_id=identity,
            attribution="用户上传；由上传者负责确认使用权",
            verification_status="VERIFIED",
        )
        a = create(db, "asset", user.id, data)
        db.commit()
        return pack(a)
    except HTTPException:
        temp.unlink(missing_ok=True)
        raise
    except Exception:
        temp.unlink(missing_ok=True)
        raise HTTPException(422, "INVALID_MEDIA: decode/type/size validation failed") from None


@router.get("/projects/{identity}/assets")
def list_assets(identity: str, db: DB, user: Actor):
    owned(db, identity, user.id, "project")
    return [
        pack(a)
        for a in db.scalars(select(Entity).where(Entity.kind == "asset", Entity.owner == user.id))
        if a.data["project_id"] == identity
    ]


@router.post("/projects/{identity}/workflow/compile")
def compile_workflow(identity: str, db: DB, user: Actor, req: CompileRequest | None = None):
    p = owned(db, identity, user.id, "project")
    if req and req.expected_version and req.expected_version != p.version:
        raise HTTPException(409, 'VERSION_CONFLICT')
    try:
        nodes = compile_plan(db, p)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return {
        "nodes": [{k: v for k, v in n.items() if k != "params"} for n in nodes],
        "timeline": canonical_timeline(p.data),
    }


@router.post("/projects/{identity}/renders", status_code=202)
def render(identity: str, req: RenderRequest, db: DB, user: Actor):
    p = owned(db, identity, user.id, "project")
    prior = db.scalar(select(Job).where(Job.owner == user.id, Job.idempotency_key == req.idempotency_key))
    if prior:
        if prior.project_id != identity or prior.revision != req.expected_version:
            raise HTTPException(409, "IDEMPOTENCY_KEY_CONFLICT")
        return {"id": prior.id, "status": prior.status}
    if p.version != req.expected_version:
        raise HTTPException(409, "VERSION_CONFLICT")
    if p.data["review_state"] != "APPROVED":
        raise HTTPException(409, "HUMAN_APPROVAL_REQUIRED")
    if db.scalar(select(Job).where(Job.owner == user.id, Job.status.in_(["READY", "RUNNING"]))):
        raise HTTPException(429, "ONE_ACTIVE_RENDER_PER_USER")
    try:
        plan = compile_plan(db, p)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    j = Job(
        owner=user.id,
        project_id=identity,
        revision=p.version,
        idempotency_key=req.idempotency_key,
        snapshot=copy.deepcopy(p.data),
    )
    db.add(j)
    db.flush()
    for n in plan:
        db.add(Node(job_id=j.id, **n))
    emit(
        db,
        j.id,
        user.id,
        "ENQUEUED",
        {"revision": p.version, "mode": "CPU_REAL", "timeline_hash": digest(canonical_timeline(p.data))},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        prior = db.scalar(select(Job).where(Job.owner == user.id, Job.idempotency_key == req.idempotency_key))
        if not prior:
            raise
        return {"id": prior.id, "status": prior.status}
    return {"id": j.id, "status": j.status}


def get_job(db, identity, user):
    j = db.get(Job, identity)
    if not j or j.owner != user.id:
        raise HTTPException(404, "Job not found")
    return j


@router.get("/jobs/{identity}")
def job_status(identity: str, db: DB, user: Actor):
    j = get_job(db, identity, user)
    nodes = db.scalars(select(Node).where(Node.job_id == identity)).all()
    for n in nodes:
        if n.state == "SUCCEEDED" and not media.valid_artifact(n.output):
            n.state = "STALE"
            j.status = "STALE"
    db.commit()
    return {
        "id": j.id,
        "status": j.status,
        "revision": j.revision,
        "nodes": [
            {
                "id": n.id,
                "key": n.key,
                "kind": n.kind,
                "state": n.state,
                "deps": n.deps,
                "attempts": n.attempts,
                "error": n.error,
                "download": f"/api/v2/artifacts/{n.id}/download" if n.state == "SUCCEEDED" else None,
            }
            for n in nodes
        ],
    }


@router.get("/jobs/{identity}/events")
def job_events(identity: str, db: DB, user: Actor):
    get_job(db, identity, user)
    return [
        {"event": e.event, "data": e.data, "time": e.created_at}
        for e in db.scalars(select(Event).where(Event.subject == identity).order_by(Event.created_at))
    ]


@router.post("/jobs/{identity}/cancel")
def cancel(identity: str, db: DB, user: Actor):
    j = get_job(db, identity, user)
    if j.status == "SUCCEEDED":
        raise HTTPException(409, "ALREADY_FINISHED")
    j.status = "CANCELLED"
    for n in db.scalars(select(Node).where(Node.job_id == identity, Node.state != "SUCCEEDED")):
        n.state = "CANCELLED"
        n.fence += 1
    emit(db, identity, user.id, "CANCELLED")
    db.commit()
    return {"status": j.status}


@router.post("/jobs/{identity}/retry")
def retry(identity: str, db: DB, user: Actor):
    j = get_job(db, identity, user)
    if j.status in {"READY", "RUNNING", "CANCELLED", "NEEDS_REVIEW"}:
        raise HTTPException(409, "RETRY_NOT_ALLOWED")
    nodes = db.scalars(select(Node).where(Node.job_id == identity)).all()
    invalid = {n.key for n in nodes if n.state != "SUCCEEDED" or not media.valid_artifact(n.output)}
    while True:
        more = invalid | {n.key for n in nodes if set(n.deps) & invalid}
        if more == invalid:
            break
        invalid = more
    for n in nodes:
        if n.key in invalid:
            n.state = "READY"
            n.attempts = 0
            n.fence += 1
            n.output = {}
            n.error = ""
    j.status = "READY"
    emit(db, identity, user.id, "RETRY", {"nodes": sorted(invalid)})
    db.commit()
    return {"status": j.status}


@router.get("/artifacts/{identity}/download")
def download(identity: str, db: DB, user: Actor):
    n = db.get(Node, identity)
    if not n:
        raise HTTPException(404, "Artifact not found")
    j = get_job(db, n.job_id, user)
    if n.state != "SUCCEEDED" or j.status != "SUCCEEDED" or not media.valid_artifact(n.output):
        raise HTTPException(409, "ARTIFACT_NOT_VERIFIED_OR_STALE")
    p = media.safe_path(n.output["storage_key"])
    return FileResponse(p, filename="百骑谱-" + n.kind + p.suffix)


@router.get("/projects/{identity}/export")
def export_project(identity: str, db: DB, user: Actor):
    p = owned(db, identity, user.id, "project")
    asset_ids = {s["asset_id"] for s in p.data["scenes"] if s["asset_id"]} | set(p.data["audio_asset_ids"])
    assets = [
        pack(a)
        for a in db.scalars(select(Entity).where(Entity.kind == "asset", Entity.owner == user.id))
        if a.id in asset_ids
    ]
    return {
        **pack(p),
        "timeline": canonical_timeline(p.data),
        "publication": "PRIVATE_NOT_PUBLISHED",
        "sources": [r for s in p.data["scenes"] for r in s["claim_refs"]],
        "assets": assets,
        "findings": check_bible(p.data),
    }


@router.get("/projects/{identity}/lineage")
def lineage(identity: str, db: DB, user: Actor):
    p = owned(db, identity, user.id, "project")
    edges = []
    for s in p.data["scenes"]:
        scene_key = f"{p.id}@{p.version}/scene/{s['id']}"
        for ref in s["claim_refs"]:
            edges.append({"from": ref, "to": scene_key, "relation": "CITES", "certainty": "direct_dependency"})
            claim_id, version = ref.rsplit("@", 1)
            record = db.scalar(select(Revision).where(Revision.entity_id == claim_id, Revision.version == int(version)))
            if record:
                data = record.data
                passage_key = data["passage_id"] + "@" + str(data["passage_version"])
                edges += [
                    {"from": passage_key, "to": ref, "relation": data["relation"], "certainty": "direct_dependency"},
                    {
                        "from": data["source_id"],
                        "to": passage_key,
                        "relation": "CONTAINS",
                        "certainty": "direct_dependency",
                    },
                ]
        if s["asset_id"]:
            edges.append({"from": s["asset_id"], "to": scene_key, "relation": "USES", "certainty": "direct_dependency"})
        edges.append(
            {
                "from": scene_key,
                "to": f"{p.id}@{p.version}/timeline",
                "relation": "COMPOSES",
                "certainty": "derived_dependency",
            }
        )
    for job in db.scalars(select(Job).where(Job.project_id == identity, Job.owner == user.id)):
        for n in db.scalars(select(Node).where(Node.job_id == job.id)):
            edges.append(
                {
                    "from": f"{identity}@{job.revision}/timeline",
                    "to": n.id,
                    "relation": "COMPILED_TO",
                    "certainty": "derived_dependency",
                }
            )
            if n.output:
                edges.append(
                    {
                        "from": n.id,
                        "to": n.output.get("sha256"),
                        "relation": "GENERATED",
                        "certainty": "direct_dependency",
                    }
                )
    return {
        "project_revision": p.version,
        "edges": edges,
        "unknown_semantic_dependencies": "REVIEW_REQUIRED",
        "representation": "Derived from immutable revisions and execution records; no second authoritative graph store",
    }
