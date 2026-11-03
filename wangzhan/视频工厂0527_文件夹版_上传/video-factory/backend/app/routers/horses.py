import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.horse import Horse
from app.models.user import User
from app.schemas.horse import HorseOut, HorseListOut
from app.services.auth import get_current_user

router = APIRouter(prefix="/horses", tags=["horses"])
SERVER_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = SERVER_DIR / "data"
LEGENDARY_HORSE_BASE_FILE = "legendary_horses_top5.json"
LEGENDARY_HORSE_BATCH_GLOB = "legendary_horses_batch*.json"
RAG_LIBRARY_TOTAL = 100


class RagLibraryProfileUpdateIn(BaseModel):
    story: str | None = None
    horse_life_story: str | None = None
    owner_life_story: str | None = None
    full_story: str | None = None
    rag_summary: str | None = None
    prompt_guidance: str | None = None
    avoid: str | None = None
    voiceover_seed: str | None = None
    visual_keywords: list[str] | str | None = None
    shot_beats: list[str] | str | None = None
    video_angles: list[str] | str | None = None
    horse_timeline: list[str] | str | None = None
    owner_timeline: list[str] | str | None = None


def _profile_paths() -> tuple[Path, ...]:
    candidates: list[Path] = [DATA_DIR / LEGENDARY_HORSE_BASE_FILE]
    candidates.extend(sorted(DATA_DIR.glob(LEGENDARY_HORSE_BATCH_GLOB)))
    resolved: list[Path] = []
    seen: set[str] = set()
    for item in candidates:
        key = str(item.resolve())
        if key in seen:
            continue
        seen.add(key)
        resolved.append(item)
    return tuple(resolved)


def _load_rag_profiles() -> tuple[dict[str, Any], ...]:
    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for path in _profile_paths():
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, list):
            continue
        default_priority = "top5" if path.name == LEGENDARY_HORSE_BASE_FILE else path.stem
        for index, row in enumerate(data, start=1):
            if not isinstance(row, dict):
                continue
            profile_id = str(row.get("id") or "").strip()
            dedupe_key = profile_id or f"{path.name}#{index}"
            if dedupe_key in seen_ids:
                continue
            seen_ids.add(dedupe_key)
            payload = dict(row)
            payload.setdefault("priority", default_priority)
            payload.setdefault("sequence", len(merged) + 1)
            merged.append(payload)
    return tuple(merged)


def _profile_key(profile: dict[str, Any]) -> tuple[str, str]:
    return (_normalize_text(profile.get("id")), _normalize_text(profile.get("name")))


def _profile_matches_horse(profile: dict[str, Any], horse: Horse) -> bool:
    profile_id, profile_name = _profile_key(profile)
    return bool(
        (profile_id and profile_id == str(horse.id))
        or (profile_name and profile_name == str(horse.name))
    )


def _find_profile_for_horse(horse: Horse) -> dict[str, Any] | None:
    for profile in _load_rag_profiles():
        if _profile_matches_horse(profile, horse):
            return profile
    return None


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = _normalize_text(value)
    return [text] if text else []


def _editable_profile_value(key: str, value: Any) -> Any:
    list_keys = {"visual_keywords", "shot_beats", "video_angles", "horse_timeline", "owner_timeline"}
    if key in list_keys:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [
            item.strip()
            for item in str(value or "").replace("；", "\n").replace(";", "\n").splitlines()
            if item.strip()
        ]
    return _normalize_text(value)


def _write_rag_profile_update(horse_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    target = _normalize_text(horse_id)
    if not target:
        raise HTTPException(status_code=400, detail="horse_id is required")
    if not updates:
        raise HTTPException(status_code=400, detail="No editable fields provided")

    for path in _profile_paths():
        if not path.exists():
            continue
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=500, detail=f"Failed to read RAG profile file: {path.name}") from exc
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            if _normalize_text(row.get("id")) != target and _normalize_text(row.get("name")) != target:
                continue
            for key, value in updates.items():
                row[key] = _editable_profile_value(key, value)
            try:
                path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError as exc:
                raise HTTPException(status_code=500, detail=f"Failed to save RAG profile file: {path.name}") from exc
            return {"file": path.name, "profile": row}

    raise HTTPException(status_code=404, detail="Horse not found in editable RAG profile files")


def _profile_story(profile: dict[str, Any] | None, horse: Horse) -> str:
    if not profile:
        return horse.story
    return (
        _normalize_text(profile.get("story"))
        or _normalize_text(profile.get("horse_life_story"))
        or _normalize_text(profile.get("owner_life_story"))
        or horse.story
    )


def _profile_full_story(profile: dict[str, Any] | None, horse: Horse) -> str:
    if not profile:
        return horse.full_story
    parts = [
        _normalize_text(profile.get("horse_life_story")),
        _normalize_text(profile.get("owner_life_story")),
    ]
    profile_life_story = "\n\n".join(part for part in parts if part)
    return _normalize_text(profile.get("full_story")) or profile_life_story or horse.full_story


def _horse_out_with_profile(horse: Horse) -> HorseOut:
    profile = _find_profile_for_horse(horse)
    payload = HorseOut.model_validate(horse).model_dump()
    if profile:
        payload["story"] = _profile_story(profile, horse)
        payload["full_story"] = _profile_full_story(profile, horse)
    return HorseOut.model_validate(payload)


def _merge_horse_profile(horse: Horse | None, profile: dict[str, Any]) -> dict[str, Any]:
    profile_id = _normalize_text(profile.get("id"))
    name = _normalize_text(profile.get("name")) or (horse.name if horse else "")
    story = _normalize_text(profile.get("story")) or (horse.story if horse else "")
    horse_life_story = _normalize_text(profile.get("horse_life_story"))
    owner_life_story = _normalize_text(profile.get("owner_life_story"))
    full_story = _normalize_text(profile.get("full_story")) or (horse.full_story if horse else "")
    image_url = _normalize_text(profile.get("image_url")) or (horse.image if horse else "")
    owner = _normalize_text(profile.get("owner")) or (horse.owner if horse else "")
    dynasty = _normalize_text(profile.get("dynasty")) or (horse.dynasty if horse else "")
    source = _normalize_text(profile.get("historical_source")) or (horse.historical_source if horse else "")
    source_type = _normalize_text(profile.get("source_type")) or "史料整理"

    traits = _normalize_text_list(profile.get("traits") or profile.get("labels"))
    if not traits and horse and isinstance(horse.traits, list):
        traits = [str(item).strip() for item in horse.traits if str(item).strip()]

    detail_text_parts = [part for part in [story, horse_life_story, owner_life_story, full_story] if part]
    detail_text = "\n\n".join(detail_text_parts)
    query_blob = " ".join(
        [
            profile_id,
            name,
            owner,
            dynasty,
            source,
            source_type,
            story,
            horse_life_story,
            owner_life_story,
            full_story,
            " ".join(traits),
        ]
    )

    return {
        "id": profile_id or (horse.id if horse else ""),
        "name": name,
        "title": _normalize_text(profile.get("trait")) or (horse.title if horse else "历史名马"),
        "rarity": horse.rarity if horse else "SSR",
        "image": image_url or "/images/chitu.png",
        "owner": owner,
        "figure": _normalize_text(profile.get("figure")) or owner,
        "dynasty": dynasty,
        "historical_source": source,
        "source_type": source_type,
        "trait": _normalize_text(profile.get("trait")) or (horse.trait if horse else "历史名马"),
        "traits": traits,
        "labels": _normalize_text_list(profile.get("labels")) or traits,
        "story": story,
        "horse_life_story": horse_life_story,
        "owner_life_story": owner_life_story,
        "full_story": full_story,
        "hook": _normalize_text(profile.get("hook")),
        "conflict": _normalize_text(profile.get("conflict")),
        "emotional_arc": _normalize_text(profile.get("emotional_arc")),
        "visual_keywords": _normalize_text_list(profile.get("visual_keywords")),
        "shot_beats": _normalize_text_list(profile.get("shot_beats")),
        "horse_timeline": _normalize_text_list(profile.get("horse_timeline")),
        "owner_timeline": _normalize_text_list(profile.get("owner_timeline")),
        "video_angles": _normalize_text_list(profile.get("video_angles")),
        "prompt_guidance": _normalize_text(profile.get("prompt_guidance")),
        "avoid": _normalize_text(profile.get("avoid")),
        "rag_summary": _normalize_text(profile.get("rag_summary")),
        "voiceover_seed": _normalize_text(profile.get("voiceover_seed")),
        "priority": _normalize_text(profile.get("priority")) or "top5",
        "sequence": int(profile.get("sequence") or 0),
        "detail_text": detail_text,
        "query_blob": query_blob.lower(),
    }


def _build_rag_library_items(db: Session) -> list[dict[str, Any]]:
    horse_rows = db.query(Horse).all()
    by_id = {str(item.id): item for item in horse_rows}
    by_name = {str(item.name): item for item in horse_rows}

    items: list[dict[str, Any]] = []
    for profile in _load_rag_profiles():
        profile_id = _normalize_text(profile.get("id"))
        profile_name = _normalize_text(profile.get("name"))
        horse = by_id.get(profile_id) or by_name.get(profile_name)
        merged = _merge_horse_profile(horse, profile)
        merged_id = _normalize_text(merged.get("id"))
        if not merged_id:
            continue
        items.append(merged)

    items.sort(key=lambda row: (int(row.get("sequence") or 0), str(row.get("id") or "")))
    return items


@router.get("/rag-library")
def list_rag_library(
    q: Optional[str] = Query(None, description="按马名/人物/朝代/关键词搜索"),
    source_type: Optional[str] = Query(None, description="按来源类型过滤"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    items = _build_rag_library_items(db)

    query = _normalize_text(q).lower()
    source_filter = _normalize_text(source_type).lower()
    if query:
        items = [row for row in items if query in str(row.get("query_blob") or "").lower()]
    if source_filter:
        items = [row for row in items if source_filter in str(row.get("source_type") or "").lower()]

    total = RAG_LIBRARY_TOTAL
    start = (page - 1) * size
    end = start + size
    sliced = items[start:end]

    # `query_blob` is internal search glue, not frontend display data.
    for row in sliced:
        row.pop("query_blob", None)

    return {"items": sliced, "total": total, "page": page, "size": size}


@router.put("/rag-library/{horse_id}")
def update_rag_library_detail(
    horse_id: str,
    req: RagLibraryProfileUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    updates = {
        key: value
        for key, value in req.model_dump(exclude_unset=True).items()
        if value is not None
    }
    saved = _write_rag_profile_update(horse_id, updates)
    target = _normalize_text(horse_id)
    for item in _build_rag_library_items(db):
        if str(item.get("id") or "") == target or str(item.get("name") or "") == target:
            item.pop("query_blob", None)
            return {"status": "updated", "file": saved["file"], "item": item}
    return {"status": "updated", "file": saved["file"], "item": saved["profile"]}


@router.get("/rag-library/stats")
def rag_library_stats(db: Session = Depends(get_db)):
    items = _build_rag_library_items(db)
    source_counter: dict[str, int] = {}
    for row in items:
        key = _normalize_text(row.get("source_type")) or "未知来源"
        source_counter[key] = source_counter.get(key, 0) + 1
    return {"total": RAG_LIBRARY_TOTAL, "sourceTypes": source_counter}


@router.get("/rag-library/{horse_id}")
def get_rag_library_detail(horse_id: str, db: Session = Depends(get_db)):
    target = _normalize_text(horse_id)
    if not target:
        raise HTTPException(status_code=400, detail="horse_id is required")

    for item in _build_rag_library_items(db):
        if str(item.get("id") or "") == target or str(item.get("name") or "") == target:
            item.pop("query_blob", None)
            return item

    raise HTTPException(status_code=404, detail="Horse not found in RAG library")


@router.get("", response_model=HorseListOut)
def list_horses(
    rarity: Optional[str] = Query(None),
    dynasty: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Horse)
    if rarity:
        query = query.filter(Horse.rarity == rarity)
    if dynasty:
        query = query.filter(Horse.dynasty == dynasty)

    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return HorseListOut(items=[_horse_out_with_profile(h) for h in items], total=total)


@router.get("/{horse_id}", response_model=HorseOut)
def get_horse(horse_id: str, db: Session = Depends(get_db)):
    horse = db.query(Horse).filter(Horse.id == horse_id).first()
    if not horse:
        raise HTTPException(status_code=404, detail="Horse not found")
    return _horse_out_with_profile(horse)
