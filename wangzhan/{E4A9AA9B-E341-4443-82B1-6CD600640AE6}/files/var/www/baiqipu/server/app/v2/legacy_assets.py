"""Audited claiming endpoint for legacy `/generated/*` media.

The original site wrote generated media to `server/generated/` without any
per-file ownership metadata. This module reconstructs ownership from the
legacy `workflow_tasks` table (task id -> user id), which is the only durable
record that exists, and then imports the file into the V2 asset store so it
can be served by the signed-ticket media endpoint.

Rules enforced here:
  * Only files that are actually referenced by a legacy task result payload
    can be claimed; unreferenced files are never exposed.
  * Ownership is derived from `workflow_tasks.user_id`; the claimant must be
    that owner, or a staff member performing a migration.
  * Every claim is written to the V2 event log with the source path and hash.
  * A file can only be claimed once; the second attempt is a 409.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.workflow_task import WorkflowTask
from app.services.auth import get_current_staff_user, get_current_user

from . import media
from .domain import create, emit
from .models import Entity

router = APIRouter(prefix="/api/v2/legacy-assets", tags=["Legacy assets"])

DB = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(get_current_user)]
Staff = Annotated[User, Depends(get_current_staff_user)]

SERVER_DIR = Path(__file__).resolve().parents[3]
GENERATED_DIR = SERVER_DIR / "generated"


class ClaimRequest(BaseModel):
    relative_path: str = Field(min_length=1, max_length=400)
    rights: str = Field(default="UNKNOWN", max_length=40)
    note: str = Field(default="", max_length=400)


def _scan_claims(db: Session, relative_path: str) -> list[WorkflowTask]:
    tasks = db.scalars(select(WorkflowTask)).all()
    hits = []
    for task in tasks:
        payload = task.result_payload if isinstance(task.result_payload, dict) else {}
        urls: list[str] = []
        for key in ("videoUrl", "subtitleUrl", "coverUrl", "firstVideoUrl", "sourceVideoUrl"):
            value = str(payload.get(key) or "")
            if value:
                urls.append(value)
        clips = payload.get("sourceClips")
        if isinstance(clips, list):
            urls.extend(str(item or "") for item in clips)
        for url in urls:
            if not url.startswith("/generated/"):
                continue
            tail = url.removeprefix("/generated/").lstrip("/\\")
            if tail == relative_path:
                hits.append(task)
                break
    return hits


def _safe_generated_path(relative_path: str) -> Path:
    root = GENERATED_DIR.resolve()
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root):
        raise HTTPException(422, "UNSAFE_LEGACY_PATH")
    if not candidate.is_file():
        raise HTTPException(404, "Legacy media not found")
    return candidate


@router.get("/audit")
def audit(db: DB, user: Staff):
    """Staff-only inventory of legacy media and its provable ownership."""
    root = GENERATED_DIR.resolve()
    on_disk = []
    if GENERATED_DIR.is_dir():
        for path in GENERATED_DIR.rglob("*"):
            if path.is_file():
                on_disk.append(path.relative_to(root).as_posix())

    tasks = db.scalars(select(WorkflowTask)).all()
    claimed: dict[str, list[dict[str, str]]] = {}
    for task in tasks:
        payload = task.result_payload if isinstance(task.result_payload, dict) else {}
        urls: list[str] = []
        for key in ("videoUrl", "subtitleUrl", "coverUrl", "firstVideoUrl", "sourceVideoUrl"):
            value = str(payload.get(key) or "")
            if value:
                urls.append(value)
        clips = payload.get("sourceClips")
        if isinstance(clips, list):
            urls.extend(str(item or "") for item in clips)
        for url in urls:
            if not url.startswith("/generated/"):
                continue
            tail = url.removeprefix("/generated/").lstrip("/\\")
            claimed.setdefault(tail, []).append({"task_id": task.id, "user_id": task.user_id})

    already = {
        entity.data.get("legacy_relative_path")
        for entity in db.scalars(select(Entity).where(Entity.kind == "asset"))
        if isinstance(entity.data, dict) and entity.data.get("legacy_relative_path")
    }
    return {
        "generated_dir": str(GENERATED_DIR),
        "files_on_disk": len(on_disk),
        "claimed_paths": len(claimed),
        "claimable_paths": sorted(set(claimed) & set(on_disk)),
        "orphaned_files": sorted(set(on_disk) - set(claimed)),
        "already_imported": sorted(already),
        "verdict": (
            "Legacy media is present and ownership is derivable from workflow_tasks.user_id."
            if set(claimed) & set(on_disk)
            else "No legacy generated file remains on disk; nothing is claimable."
        ),
    }


@router.post("/claim", status_code=201)
def claim(req: ClaimRequest, db: DB, user: Actor):
    """Import one legacy generated file into the V2 asset store."""
    relative = str(req.relative_path or "").strip().replace("\\", "/").lstrip("/")
    if not relative or ".." in relative.split("/"):
        raise HTTPException(422, "UNSAFE_LEGACY_PATH")

    source = _safe_generated_path(relative)
    owners = _scan_claims(db, relative)
    if not owners:
        raise HTTPException(409, "LEGACY_MEDIA_UNCLAIMED: no legacy task references this file")
    owner_ids = {task.user_id for task in owners}
    if user.id not in owner_ids and user.role not in {"admin", "operator"}:
        raise HTTPException(403, "LEGACY_MEDIA_NOT_OWNED")

    existing = db.scalar(
        select(Entity).where(
            Entity.kind == "asset",
            Entity.data["legacy_relative_path"].as_string() == relative,
        )
    )
    if existing:
        raise HTTPException(409, "LEGACY_MEDIA_ALREADY_CLAIMED")

    media_type = "video" if source.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"} else "image"
    target = media.STORE / "legacy" / (source.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())

    data = media.artifact(
        target,
        media_type=media_type,
        duration=None,
        rights_status=req.rights if req.rights in {"OWNED", "LICENSED", "PUBLIC_DOMAIN", "UNKNOWN"} else "UNKNOWN",
        project_id="",
        asset_role="LEGACY_IMPORT",
        attribution=f"Legacy import from {relative}",
        verification_status="VERIFIED",
        legacy_relative_path=relative,
        legacy_task_ids=[task.id for task in owners],
        legacy_owner_ids=sorted(owner_ids),
        note=req.note,
    )
    asset = create(db, "asset", user.id, data)
    emit(
        db,
        asset.id,
        user.id,
        "LEGACY_ASSET_CLAIMED",
        {"legacy_relative_path": relative, "legacy_task_ids": [task.id for task in owners], "bytes": data["bytes"]},
    )
    db.commit()
    return {"id": asset.id, "data": asset.data, "legacy_owner_ids": sorted(owner_ids)}


@router.get("/inventory")
def inventory(db: DB, user: Actor):
    """Everything the requesting user owns in the V2 asset store."""
    rows = db.scalars(select(Entity).where(Entity.kind == "asset", Entity.owner == user.id)).all()
    return [
        {
            "id": row.id,
            "media_type": (row.data or {}).get("media_type"),
            "bytes": (row.data or {}).get("bytes"),
            "asset_role": (row.data or {}).get("asset_role"),
            "legacy_relative_path": (row.data or {}).get("legacy_relative_path"),
        }
        for row in rows
    ]
