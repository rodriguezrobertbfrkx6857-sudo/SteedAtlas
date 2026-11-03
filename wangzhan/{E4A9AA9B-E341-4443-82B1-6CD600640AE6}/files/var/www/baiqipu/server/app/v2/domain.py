import copy
import hashlib
import json
import math
import re
from collections import Counter

from fastapi import HTTPException
from sqlalchemy import update

from .contracts import Project
from .models import Entity, Event, Revision


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def emit(db, subject, actor, event, data=None):
    db.add(Event(subject=subject, actor=actor, event=event, data=data or {}))


def create(db, kind, owner, data, entity_id=None):
    entity = Entity(kind=kind, owner=owner, data=data, version=1)
    if entity_id:
        entity.id = entity_id
    db.add(entity)
    db.flush()
    db.add(Revision(entity_id=entity.id, version=1, actor=owner, data=data))
    emit(db, entity.id, owner, "CREATED", {"kind": kind, "hash": digest(data)})
    return entity


def revise(db, entity, expected, data, actor):
    changed = db.execute(
        update(Entity).where(Entity.id == entity.id, Entity.version == expected).values(version=expected + 1, data=data)
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "VERSION_CONFLICT: reload the latest revision")
    db.add(Revision(entity_id=entity.id, version=expected + 1, actor=actor, data=data))
    emit(db, entity.id, actor, "REVISED", {"version": expected + 1, "hash": digest(data)})
    db.flush()
    db.refresh(entity)
    return entity


def owned(db, entity_id, owner, kind=None):
    e = db.get(Entity, entity_id)
    if not e or e.owner != owner or (kind and e.kind != kind):
        raise HTTPException(404, "Resource not found")
    return e


def pack(e):
    return {"id": e.id, "kind": e.kind, "version": e.version, "data": e.data}


def tokens(text):
    text = text.lower().translate(str.maketrans("呂馬盧烏騅關劉備漢傳騎", "吕马卢乌骓关刘备汉传骑"))
    result = re.findall(r"[a-z0-9]+", text)
    for chunk in re.findall(r"[\u4e00-\u9fff]+", text):
        result.extend(chunk)
        result.extend(chunk[i : i + 2] for i in range(len(chunk) - 1))
    return result


ALIASES = {"赤菟": "赤兔", "赤兔马": "赤兔", "乌骓马": "乌骓", "的颅": "的卢", "的顱": "的卢"}


def rank(query, documents, mode="bm25"):
    for alias, canonical in ALIASES.items():
        query = query.replace(alias, canonical)
    query_terms = Counter(tokens(query))
    bags = [Counter(tokens(d["text"])) for d in documents]
    avg = sum(sum(b.values()) for b in bags) / max(len(bags), 1)
    scores = []
    for doc, bag in zip(documents, bags):
        score = 0
        if mode == "cosine":
            den = math.sqrt(sum(x * x for x in bag.values()) * sum(x * x for x in query_terms.values()))
            score = sum(bag[t] * n for t, n in query_terms.items()) / den if den else 0
        else:
            for term in query_terms:
                df = sum(term in b for b in bags)
                tf = bag[term]
                idf = math.log(1 + (len(bags) - df + 0.5) / (df + 0.5))
                score += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * sum(bag.values()) / (avg or 1)))
        if score > 0:
            scores.append({**doc, "score": score})
    return sorted(scores, key=lambda d: d["score"], reverse=True)


def check_bible(project):
    issues = []
    for s in project["scenes"]:
        if project["bible"].get("period") and s.get("period") and s["period"] != project["bible"]["period"]:
            issues.append({"scene_id": s["id"], "code": "PERIOD_CONFLICT"})
        if s["label"] != "CREATIVE" and not s["claim_refs"]:
            issues.append({"scene_id": s["id"], "code": "MISSING_CITATION"})
    return issues


def select_roles(project, intent):
    if intent == "subtitle":
        return [], ["SUBTITLE_ONLY_NO_REASONING"]
    roles, reasons = [], []
    if intent == "evidence" or any(s["label"] != "CREATIVE" and not s["claim_refs"] for s in project["scenes"]):
        roles.append("RESEARCH")
        reasons.append("EVIDENCE_GAP")
    if any(not s["text"].strip() for s in project["scenes"]):
        roles.append("NARRATIVE")
        reasons.append("SCRIPT_GAP")
    if intent == "plan":
        roles.append("DIRECTOR")
        reasons.append("SCENE_PLAN_REQUESTED")
    if intent == "repair":
        roles.append("REPAIR")
        reasons.append("REPAIR_REQUESTED")
    if roles or check_bible(project):
        roles.append("REVIEW")
        reasons.append("HUMAN_REVIEW_REQUIRED")
    return roles, reasons


def rule_proposal(project, intent):
    roles, reasons = select_roles(project, intent)
    # The rule tool proposes only a style field; it cannot grant approval or rewrite facts.
    patches = [{"path": "/bible/style", "value": "克制的数字博物馆编辑风格"}] if "DIRECTOR" in roles else []
    return {
        "mode": "RULE_BASED",
        "roles": roles,
        "reason_codes": reasons,
        "patches": patches,
        "findings": check_bible(project),
        "tool_calls": ["inspect_timeline", "get_scene_bible", "validate_citations"],
        "input_hash": digest(project),
        "policy_version": "controller-1",
        "review_state": "PENDING",
        "tool_results": [
            {"tool": "inspect_timeline", "output_hash": digest(canonical_timeline(project))},
            {"tool": "get_scene_bible", "output_hash": digest(project["bible"])},
            {"tool": "check_scene_constraints", "output": check_bible(project)},
        ],
    }


def accept_patches(project, patches):
    new = copy.deepcopy(project)
    for patch in patches:
        if patch["path"] != "/bible/style" or not isinstance(patch["value"], str) or len(patch["value"]) > 160:
            raise HTTPException(422, "FORBIDDEN_PATCH_PATH")
        new["bible"]["style"] = patch["value"]
    new["review_state"] = "DRAFT"
    return Project.model_validate(new).model_dump()


def impact(before, after, change="project"):
    result = {}
    old = {s["id"]: s for s in before["scenes"]}
    for s in after["scenes"]:
        previous = old.get(s["id"])
        if (
            change == "claim"
            or not previous
            or previous["claim_refs"] != s["claim_refs"]
            or previous["label"] != s["label"]
        ):
            decision = "REVIEW_REQUIRED"
        elif before["bible"] != after["bible"] or any(before[k] != after[k] for k in ["width", "height", "fps_num"]):
            decision = "REBUILD_REQUIRED"
        elif previous != s:
            decision = "REBUILD_REQUIRED"
        else:
            decision = "REUSE_ALLOWED"
        result[s["id"]] = {
            "decision": decision,
            "asset": "REUSE_ALLOWED" if previous and previous["asset_id"] == s["asset_id"] else "REBUILD_REQUIRED",
        }
    return result


def canonical_timeline(project):
    cursor = 0
    clips, cues = [], []
    for s in project["scenes"]:
        end = cursor + s["duration_ticks"]
        clips.append(
            {
                "clip_id": s["id"],
                "scene_id": s["id"],
                "asset_id": s["asset_id"],
                "start_tick": cursor,
                "end_tick": end,
                "source_in_tick": 0,
                "claim_refs": s["claim_refs"],
            }
        )
        cues.append({"cue_id": s["id"], "start_tick": cursor, "end_tick": end, "text": s["text"], "label": s["label"]})
        cursor = end
    return {
        "schema_version": 1,
        "fps_num": project["fps_num"],
        "fps_den": 1,
        "width": project["width"],
        "height": project["height"],
        "duration_ticks": cursor,
        "tracks": [
            {"kind": "VISUAL", "clips": clips},
            {"kind": "NARRATION", "assets": project["audio_asset_ids"]},
            {"kind": "SUBTITLE", "cues": cues},
        ],
        "alignment": "MANUAL_SCENE_TIMING",
    }
