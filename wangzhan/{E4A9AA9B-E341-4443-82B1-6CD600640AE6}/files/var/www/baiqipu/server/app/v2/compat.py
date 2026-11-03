"""V2-backed compatibility adapter for the original video factory frontend.

The original `workflow-studio/app.js` talks to the legacy `/api/v1/video/workflow`
contract. Rather than rewriting 5,000+ lines of readable frontend code, this module
implements the exact same wire shapes on top of the V2 domain model
(`CreativeProject` + `Job` + DAG worker), so the original UI keeps working while
all rendering happens locally on CPU through the V2 DAG.

Nothing here calls an external provider. External video generation stays frozen.
"""

from __future__ import annotations

import copy
import time
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.auth import get_current_user

from . import media
from .contracts import Project, Scene
from .domain import canonical_timeline, create, digest, emit, revise
from .models import Entity, Event, Job, Node
from .runtime import compile_plan
from .security import issue_media_ticket, verify_media_ticket

router = APIRouter(prefix="/api/v2/compat/workflow", tags=["Video factory compat"])

DB = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(get_current_user)]

# Frontend node order is fixed by the original workflow-studio canvas.
FRONTEND_NODE_SEQUENCE = [
    "reference_input",
    "reference_analyze",
    "input",
    "script",
    "storyboard",
    "voice",
    "keyframe",
    "subtitle",
    "veo",
    "compose",
    "output",
    "xhs_publish",
]

ASPECT_RESOLUTIONS = {
    "9:16": (720, 1280),
    "16:9": (1280, 720),
    "1:1": (1080, 1080),
}

NARRATIVE_BEATS = [
    "开场悬念：{title}，一句反问把观众拽进故事。",
    "背景铺陈：{horse}出现在这段历史里，身份与处境先说清楚。",
    "冲突升级：人与马之间出现变化，节奏开始收紧。",
    "关键推进：{brief}",
    "转折时刻：史料与传说在这里交汇，真相只露出一角。",
    "收束余味：把判断留给观众，也把这段记忆留下。",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def _clip(value: Any, limit: int = 240) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _aspect_resolution(aspect: str) -> tuple[int, int]:
    return ASPECT_RESOLUTIONS.get(str(aspect or "9:16").strip(), ASPECT_RESOLUTIONS["9:16"])


def _planned_scenes(payload: dict[str, Any], fps_num: int) -> list[dict[str, Any]]:
    """Deterministic local planning. No model call, no external provider."""
    topic = _clip(payload.get("topic") or payload.get("title"), 80) or "一匹名马的故事"
    horse = _clip(payload.get("horse") or payload.get("horse_name"), 40) or "赤兔"
    brief = _clip(payload.get("brief"), 160)
    script = payload.get("script") if isinstance(payload.get("script"), dict) else {}
    storyboard = payload.get("storyboard") if isinstance(payload.get("storyboard"), dict) else {}
    custom = _clip(script.get("customPrompt"), 120)

    shot_count = max(1, min(12, int(storyboard.get("shotCount") or 5) or 5))
    shot_seconds = max(2, min(12, int(storyboard.get("shotSeconds") or 6) or 6))

    scenes: list[dict[str, Any]] = []
    for index in range(shot_count):
        beat = NARRATIVE_BEATS[index % len(NARRATIVE_BEATS)].format(title=topic, horse=horse, brief=brief or topic)
        if index >= len(NARRATIVE_BEATS):
            beat = f"补充镜头 {index + 1}：{topic}的细节继续推进。"
        if custom and index == 0:
            beat = f"{beat} 补充要求：{custom}"
        scenes.append(
            {
                "id": f"scene{index + 1}",
                "text": _clip(beat, 240),
                "duration_ticks": shot_seconds * fps_num,
                "asset_id": None,
                "claim_refs": [],
                "label": "CREATIVE",
                "period": "",
            }
        )
    return scenes


def _reference_asset_id(payload: dict[str, Any]) -> str | None:
    reference = payload.get("reference") if isinstance(payload.get("reference"), dict) else {}
    media_url = str(reference.get("mediaUrl") or "").strip()
    if "/api/v2/compat/workflow/media/asset-" not in media_url:
        return None
    tail = media_url.split("/api/v2/compat/workflow/media/", 1)[1]
    identity = tail.split("?", 1)[0].strip()
    return identity[len("asset-") :] if identity.startswith("asset-") else None


def _build_project(payload: dict[str, Any], horse_name: str, asset_id: str | None) -> Project:
    width, height = _aspect_resolution(payload.get("aspect_ratio") or "9:16")
    fps_num = 24
    scenes = _planned_scenes(payload, fps_num)
    if asset_id and scenes:
        scenes[0]["asset_id"] = asset_id
    return Project(
        title=_clip(payload.get("title") or payload.get("topic") or "百骑谱成片", 100),
        horse_id=_clip(horse_name or "chitu", 64),
        scenes=[Scene.model_validate(item) for item in scenes],
        bible={"style": "数字博物馆", "period": "", "identity": _clip(horse_name or "赤兔", 60)},
        width=width,
        height=height,
        fps_num=fps_num,
        review_state="DRAFT",
    )


def _compat_task(db: Session, identity: str, owner: str) -> Entity:
    entity = db.get(Entity, identity)
    if not entity or entity.kind != "compat_task" or entity.owner != owner:
        raise HTTPException(404, "Workflow task not found")
    return entity


def _job_for_task(db: Session, data: dict[str, Any], owner: str) -> Job | None:
    job_id = data.get("job_id")
    if not job_id:
        return None
    job = db.get(Job, job_id)
    if not job or job.owner != owner:
        return None
    return job


def _job_status_to_frontend(status: str) -> str:
    mapping = {
        "READY": "queued",
        "RUNNING": "processing",
        "SUCCEEDED": "completed",
        "CANCELLED": "cancelled",
        "FAILED_FINAL": "failed",
        "NEEDS_REVIEW": "failed",
        "STALE": "failed",
    }
    return mapping.get(str(status or ""), "queued")


def _node_states(db: Session, job: Job | None, has_reference: bool) -> list[dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    nodes = db.scalars(select(Node).where(Node.job_id == job.id)).all() if job else []
    segments = [n for n in nodes if n.kind == "segment"]
    segments_done = bool(segments) and all(n.state == "SUCCEEDED" for n in segments)
    subtitle_node = next((n for n in nodes if n.kind == "subtitle"), None)
    compose_node = next((n for n in nodes if n.kind == "compose"), None)
    job_status = str(job.status if job else "")

    def state(node_id: str, status: str, progress: int, output: dict[str, Any] | None = None) -> None:
        states[node_id] = {
            "node_id": node_id,
            "label": node_id,
            "type": node_id,
            "status": status,
            "progress": max(0, min(100, int(progress))),
            "output": output or {},
        }

    pending = "pending"
    if job is None:
        state("input", "completed", 100)
        state("script", "completed", 100)
        state("storyboard", "completed", 100)
        state("voice", "completed", 100, {"mode": "SILENT", "note": "本地成片不含人声旁白，字幕由站内 SRT 提供。"})
        state("keyframe", pending, 0)
        state("subtitle", pending, 0)
        state("veo", pending, 0)
        state("compose", pending, 0)
        state("output", pending, 0)
        state("reference_input", "completed" if has_reference else pending, 100 if has_reference else 0)
        state("reference_analyze", "completed" if has_reference else pending, 100 if has_reference else 0)
        state("xhs_publish", pending, 0, {"publication": "PRIVATE_NOT_PUBLISHED"})
    else:
        running = job_status in {"READY", "RUNNING"}
        progress = 100 if job_status == "SUCCEEDED" else (50 if job_status == "RUNNING" else 10)
        state("input", "completed", 100)
        state("script", "completed", 100)
        state("storyboard", "completed", 100)
        state("voice", "completed", 100, {"mode": "SILENT", "note": "本地成片不含人声旁白，字幕由站内 SRT 提供。"})
        state("keyframe", "completed" if segments_done else ("processing" if running else pending), 100 if segments_done else progress)
        state("veo", "completed" if segments_done else ("processing" if running else pending), 100 if segments_done else progress)
        state(
            "subtitle",
            "completed" if subtitle_node and subtitle_node.state == "SUCCEEDED" else ("processing" if running else pending),
            100 if subtitle_node and subtitle_node.state == "SUCCEEDED" else progress,
        )
        state(
            "compose",
            "completed" if compose_node and compose_node.state == "SUCCEEDED" else ("processing" if running else pending),
            100 if compose_node and compose_node.state == "SUCCEEDED" else progress,
        )
        state("output", "completed" if job_status == "SUCCEEDED" else ("processing" if running else pending), progress)
        state("reference_input", "completed" if has_reference else pending, 100 if has_reference else 0)
        state("reference_analyze", "completed" if has_reference else pending, 100 if has_reference else 0)
        state(
            "xhs_publish",
            pending,
            0,
            {"publication": "PRIVATE_NOT_PUBLISHED", "note": "发布动作在 V2 默认冻结，未执行任何外部发布。"},
        )
    return [states[node_id] for node_id in FRONTEND_NODE_SEQUENCE]


def _media_url(identity: str, owner: str, ttl_seconds: int = 3600) -> str:
    ticket = issue_media_ticket(identity, owner, ttl_seconds)
    return f"/api/v2/compat/workflow/media/{identity}?t={ticket}"


def _artifact_url(node: Node | None, owner: str) -> str:
    if not node or not node.output:
        return ""
    identity = f"node-{node.id}"
    return _media_url(identity, owner)


def _result_payload(db: Session, job: Job | None, owner: str) -> dict[str, Any]:
    if not job:
        return {}
    nodes = db.scalars(select(Node).where(Node.job_id == job.id)).all()
    compose_node = next((n for n in nodes if n.kind == "compose"), None)
    subtitle_node = next((n for n in nodes if n.kind == "subtitle"), None)
    segments = sorted(
        (n for n in nodes if n.kind == "segment"), key=lambda n: int(n.params.get("index") or 0)
    )
    payload: dict[str, Any] = {
        "engine": "STEEDATLAS V2 CPU",
        "note": "本地 CPU 合成完成，未调用任何外部生成接口。",
    }
    video_url = _artifact_url(compose_node, owner)
    if video_url:
        payload["videoUrl"] = video_url
        payload["firstVideoUrl"] = video_url
    clip_urls = [_artifact_url(node, owner) for node in segments if node.state == "SUCCEEDED"]
    if clip_urls:
        payload["sourceClips"] = clip_urls
        payload["clips"] = [{"url": url, "videoUrl": url} for url in clip_urls]
    srt_url = _artifact_url(subtitle_node, owner)
    if srt_url:
        payload["subtitleUrl"] = srt_url
        payload["srtUrl"] = srt_url
    if compose_node and compose_node.output:
        payload["duration"] = compose_node.output.get("duration")
        payload["width"] = compose_node.output.get("width")
        payload["height"] = compose_node.output.get("height")
    return payload


def _serialize_task(db: Session, entity: Entity) -> dict[str, Any]:
    data = dict(entity.data or {})
    job = _job_for_task(db, data, entity.owner)
    status = _job_status_to_frontend(job.status) if job else str(data.get("status") or "draft")
    progress = 100 if status == "completed" else (40 if status == "processing" else (10 if status == "queued" else 0))
    result_payload = _result_payload(db, job, entity.owner) if job else {}
    error_message = None
    if job and job.status in {"FAILED_FINAL", "NEEDS_REVIEW", "STALE"}:
        failed = next((n for n in db.scalars(select(Node).where(Node.job_id == job.id)).all() if n.state != "SUCCEEDED"), None)
        error_message = (failed.error if failed else "") or "本地渲染失败，请重试。"
    return {
        "task_id": entity.id,
        "title": data.get("title") or "百骑谱成片",
        "horse_name": data.get("horse_name"),
        "status": status,
        "progress": progress,
        "current_node": data.get("current_node") or "compose",
        "aspect_ratio": data.get("aspect_ratio") or "9:16",
        "duration": int(data.get("duration") or 30),
        "webhook_url": None,
        "callback_url": "",
        "callback_token": "",
        "n8n_execution_id": None,
        "workflow_definition": data.get("workflow_definition") or {},
        "input_payload": data.get("input_payload") or {},
        "normalized_payload": data.get("normalized_payload") or {},
        "node_states": _node_states(db, job, bool(data.get("reference_asset_id"))),
        "result_payload": result_payload,
        "dispatch_response": data.get("dispatch_response") or {},
        "runtime_state": {
            "taskId": entity.id,
            "status": status,
            "currentNode": data.get("current_node") or "compose",
            "activeNodes": [],
            "nodeStates": _node_states(db, job, bool(data.get("reference_asset_id"))),
            "events": [],
        },
        "error_message": error_message,
        "created_at": entity.created_at if hasattr(entity, "created_at") else _now_iso(),
        "updated_at": _now_iso(),
    }


def _enqueue_render(db: Session, entity: Entity, project: Entity) -> Job:
    """Approve (operator-initiated) and enqueue one CPU render job."""
    project_data = dict(project.data or {})
    project_data["review_state"] = "APPROVED"
    revise(db, project, project.version, project_data, entity.owner)
    emit(
        db,
        project.id,
        entity.owner,
        "CREATIVE_RENDER_REQUESTED",
        {"version": project.version, "source": "compat/video-factory", "task_id": entity.id},
    )
    plan = compile_plan(db, project)
    counter = int((entity.data or {}).get("render_count") or 0) + 1
    job = Job(
        owner=entity.owner,
        project_id=project.id,
        revision=project.version,
        idempotency_key=f"compat-{entity.id}-{counter}",
        snapshot=copy.deepcopy(project.data),
    )
    db.add(job)
    db.flush()
    for node in plan:
        db.add(Node(job_id=job.id, **node))
    emit(
        db,
        job.id,
        entity.owner,
        "ENQUEUED",
        {"revision": project.version, "mode": "CPU_REAL", "task_id": entity.id, "timeline_hash": digest(canonical_timeline(project.data))},
    )
    data = dict(entity.data or {})
    data["job_id"] = job.id
    data["render_count"] = counter
    data["status"] = "queued"
    data["current_node"] = "compose"
    entity.data = data
    db.flush()
    return job


@router.get("/provider-status")
def provider_status(user: Actor, db: DB):
    """Local CPU engine is the only configured provider. External APIs stay frozen."""
    base = {
        "mode": "v2-local-cpu",
        "external": False,
        "note": "视频工厂当前只使用站内 CPU 渲染；外部生成接口保持冻结。",
        "runtime": {"enabled": True, "connected": bool((pulse := db.get(Entity, 'local-worker-heartbeat')) and
                    time.time() - pulse.data.get('last_seen', 0) < 300), "mode": "v2-dag-worker"},
        "mediaBaseUrl": "/api/v2/compat/workflow/media",
        "downloadRemoteMedia": False,
        "xhs": {
            "configured": False,
            "enabled": False,
            "baseUrl": "",
            "publishPath": "",
            "autoCommentPath": "",
            "collectCommentsPath": "",
            "cookiePath": "",
            "cookieConfigured": False,
            "defaultVisibility": "仅自己可见",
            "defaultCommentText": "",
            "defaultCommentLimit": 0,
        },
        "tts": {"configured": False, "provider": "none", "language": "zh-CN", "fallback": "站内 SRT 字幕"},
    }
    base["gpt"] = {
        "configured": True,
        "external": False,
        "baseUrlSet": False,
        "model": "steedatlas-local-planner",
        "apiPath": "",
        "apiStyle": "local-rule",
        "note": "本地确定性分镜规划，不调用外部大模型。",
    }
    base["image"] = {
        "configured": True,
        "external": False,
        "baseUrlSet": False,
        "model": "steedatlas-template-plate",
        "apiPath": "",
        "size": "1280x720",
        "note": "程序化绘制的展陈模板画面，无外部图片调用。",
    }
    base["veo"] = {
        "configured": True,
        "external": False,
        "baseUrlSet": False,
        "model": "steedatlas-cpu-ffmpeg",
        "apiPath": "",
        "statusApiPath": "",
        "requestFormat": "local",
        "generateAudio": False,
        "maxClipsPerTask": 12,
        "waitForCompletion": True,
        "note": "本地 FFmpeg CPU 渲染，不调用外部视频模型。",
    }
    base["asr"] = {"enabled": False, "configured": False, "baseUrlSet": False, "model": "", "apiPath": "", "language": "zh"}
    return base


@router.get("/provider-models")
def provider_models(user: Actor):
    def block(model_id: str, label: str) -> dict[str, Any]:
        return {
            "configured": True,
            "baseUrlSet": False,
            "defaultModel": model_id,
            "models": [{"id": model_id, "label": label, "qualityHint": "本地稳定", "source": "local"}],
            "error": "",
        }

    return {
        "updatedAt": time.time(),
        "gpt": block("steedatlas-local-planner", "steedatlas-local-planner · 本地规划"),
        "image": block("steedatlas-template-plate", "steedatlas-template-plate · 程序化画面"),
        "veo": block("steedatlas-cpu-ffmpeg", "steedatlas-cpu-ffmpeg · CPU 渲染"),
        "asr": {"configured": False, "baseUrlSet": False, "defaultModel": "", "models": [], "error": "未启用语音识别"},
    }


@router.post("/reference/upload")
async def upload_reference(
    db: DB,
    user: Actor,
    file: UploadFile = File(...),
):
    temp = media.STORE / (uuid.uuid4().hex + ".upload")
    total = 0
    try:
        with temp.open("wb") as handle:
            while block := await file.read(1024 * 1024):
                total += len(block)
                if total > 30 * 1024 * 1024:
                    raise HTTPException(413, "UPLOAD_TOO_LARGE")
                handle.write(block)
        if not total:
            raise HTTPException(422, "EMPTY_UPLOAD")
        metadata = media.validate_upload(temp)
    except HTTPException:
        temp.unlink(missing_ok=True)
        raise
    except Exception:
        temp.unlink(missing_ok=True)
        raise HTTPException(422, "INVALID_MEDIA: decode/type/size validation failed") from None

    suffix = {
        "image": ".png",
        "video": ".mp4",
        "audio": ".m4a",
    }.get(metadata["media_type"], ".bin")
    target = media.STORE / "references" / (uuid.uuid4().hex + suffix)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(temp.read_bytes())
    temp.unlink(missing_ok=True)

    data = media.artifact(
        target,
        **metadata,
        rights_status="UNKNOWN",
        project_id="",
        asset_role="REFERENCE",
        attribution="用户上传；由上传者负责确认使用权",
        verification_status="VERIFIED",
    )
    asset = create(db, "asset", user.id, data)
    db.commit()
    identity = f"asset-{asset.id}"
    return {
        "status": "uploaded",
        "mediaType": metadata["media_type"],
        "fileName": target.name,
        "contentType": file.content_type or "",
        "sizeBytes": total,
        "mediaUrl": _media_url(identity, user.id),
        "localPath": "",
        "message": "参考素材已上传到站内素材库。",
    }


@router.post("/tasks")
def create_task(payload: dict[str, Any], db: DB, user: Actor):
    title = str(payload.get("title") or "").strip() or "百骑谱成片"
    horse_name = str(payload.get("horse_name") or "").strip()
    input_payload = payload.get("input_payload") if isinstance(payload.get("input_payload"), dict) else {}
    duration = int(payload.get("duration") or 30)
    aspect_ratio = str(payload.get("aspect_ratio") or "9:16").strip()
    workflow_definition = payload.get("workflow_definition") if isinstance(payload.get("workflow_definition"), dict) else {}

    asset_id = _reference_asset_id(input_payload)
    if asset_id:
        asset = db.get(Entity, asset_id)
        if (
            not asset
            or asset.kind != "asset"
            or asset.owner != user.id
            or (asset.data or {}).get("media_type") not in {"image", "video"}
            or not media.valid_artifact(asset.data or {})
        ):
            asset_id = None

    project_data = _build_project(input_payload or {"title": title}, horse_name, asset_id).model_dump()
    project_data["review_state"] = "DRAFT"
    from .knowledge import EvidenceSearch, KnowledgeRepository
    evidence_bundle = EvidenceSearch(KnowledgeRepository(db)).search(horse_name or title, 'all')
    # Creative script remains creative; metadata is a research input, never auto-approved facts.
    project_data['knowledge_bundle'] = {k: v for k, v in evidence_bundle.items() if k != 'editorial'}
    project = create(db, "project", user.id, project_data)
    db.flush()

    task_data = {
        "title": title,
        "horse_name": horse_name or None,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "workflow_definition": workflow_definition,
        "input_payload": input_payload,
        "normalized_payload": {"source": "steedatlas-v2-compat", "engine": "CPU_REAL"},
        "project_id": project.id,
        "reference_asset_id": asset_id,
        "status": "draft",
        "current_node": "compose",
        "dispatch_response": {"execution_mode": "v2-local-cpu", "message": "站内 V2 CPU 工作台"},
    }
    entity = create(db, "compat_task", user.id, task_data)

    auto_start = bool(payload.get("auto_start", True))
    if auto_start:
        _enqueue_render(db, entity, project)
    db.commit()
    db.refresh(entity)
    return {
        "task": _serialize_task(db, entity),
        "dispatch_status": "queued" if auto_start else "created",
        "message": "已提交到站内 V2 本地 CPU 工作台。" if auto_start else "任务已创建，等待运行。",
    }


@router.get("/tasks")
def list_tasks(db: DB, user: Actor, limit: int = Query(default=20, ge=1, le=100)):
    rows = db.scalars(
        select(Entity)
        .where(Entity.kind == "compat_task", Entity.owner == user.id)
        .order_by(Entity.id.desc())
        .limit(limit)
    ).all()
    rows = sorted(rows, key=lambda item: (item.data or {}).get("created_at") or "", reverse=True)
    return {"items": [_serialize_task(db, row) for row in rows]}


@router.get("/tasks/{task_id}")
def get_task(task_id: str, db: DB, user: Actor):
    return _serialize_task(db, _compat_task(db, task_id, user.id))


@router.get("/tasks/{task_id}/runtime")
def get_task_runtime(task_id: str, db: DB, user: Actor):
    entity = _compat_task(db, task_id, user.id)
    data = dict(entity.data or {})
    job = _job_for_task(db, data, entity.owner)
    events = []
    if job:
        events = [
            {"event": e.event, "data": e.data, "time": e.created_at}
            for e in db.scalars(select(Event).where(Event.subject == job.id).order_by(Event.created_at)).all()
        ]
    return {
        "taskId": entity.id,
        "status": _job_status_to_frontend(job.status) if job else "draft",
        "currentNode": data.get("current_node") or "compose",
        "activeNodes": [],
        "nodeStates": _node_states(db, job, bool(data.get("reference_asset_id"))),
        "events": events,
    }


@router.post("/tasks/{task_id}/run")
def run_task(task_id: str, db: DB, user: Actor):
    entity = _compat_task(db, task_id, user.id)
    data = dict(entity.data or {})
    project = db.get(Entity, data.get("project_id"))
    if not project or project.kind != "project" or project.owner != user.id:
        raise HTTPException(404, "Workflow task not found")
    job = _enqueue_render(db, entity, project)
    db.commit()
    db.refresh(entity)
    return {
        "task": _serialize_task(db, entity),
        "dispatch_status": "queued",
        "message": "已重新提交到本地 CPU 渲染队列。",
        "job_id": job.id,
    }


@router.post("/tasks/{task_id}/clear")
def clear_task(task_id: str, db: DB, user: Actor):
    entity = _compat_task(db, task_id, user.id)
    data = dict(entity.data or {})
    job = _job_for_task(db, data, entity.owner)
    if job and job.status not in {"SUCCEEDED", "CANCELLED"}:
        job.status = "CANCELLED"
        for node in db.scalars(select(Node).where(Node.job_id == job.id, Node.state != "SUCCEEDED")):
            node.state = "CANCELLED"
            node.fence += 1
        emit(db, job.id, entity.owner, "CANCELLED", {"task_id": entity.id})
    data["status"] = "cancelled"
    data["job_id"] = ""
    entity.data = data
    db.commit()
    db.refresh(entity)
    return {
        "task": _serialize_task(db, entity),
        "status": "cancelled",
        "removed_files": [],
        "message": "当前工作流已取消；已完成的渲染产物仍保留在素材库中。",
    }


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str, db: DB, user: Actor):
    entity = _compat_task(db, task_id, user.id)
    data = dict(entity.data or {})
    job = _job_for_task(db, data, entity.owner)
    if job and job.status not in {"SUCCEEDED", "CANCELLED"}:
        job.status = "CANCELLED"
        emit(db, job.id, entity.owner, "CANCELLED", {"task_id": entity.id, "reason": "task deleted"})
    db.delete(entity)
    db.commit()
    return {"status": "deleted", "task_id": task_id, "removed_files": [], "message": "任务历史已删除。"}


@router.delete("/tasks")
def delete_all_tasks(db: DB, user: Actor):
    rows = db.scalars(select(Entity).where(Entity.kind == "compat_task", Entity.owner == user.id)).all()
    for entity in rows:
        data = dict(entity.data or {})
        job = _job_for_task(db, data, entity.owner)
        if job and job.status not in {"SUCCEEDED", "CANCELLED"}:
            job.status = "CANCELLED"
        db.delete(entity)
    db.commit()
    return {
        "status": "deleted",
        "deleted_count": len(rows),
        "task_ids": [entity.id for entity in rows],
        "removed_files": [],
        "message": "全部任务历史已删除。",
    }


@router.get("/tasks/{task_id}/download")
def download_task(task_id: str, db: DB, user: Actor):
    entity = _compat_task(db, task_id, user.id)
    data = dict(entity.data or {})
    job = _job_for_task(db, data, entity.owner)
    if not job or job.status != "SUCCEEDED":
        raise HTTPException(409, "Video is not ready for download")
    compose_node = db.scalar(select(Node).where(Node.job_id == job.id, Node.key == "compose"))
    if not compose_node or not compose_node.output or not media.valid_artifact(compose_node.output):
        raise HTTPException(409, "Video is not ready for download")
    path = media.safe_path(compose_node.output["storage_key"])
    title = str(data.get("title") or "video").strip()
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in title)[:48].strip("_") or "video"
    return FileResponse(path, media_type="video/mp4", filename=f"{safe}.mp4")


@router.get("/media/{identity}")
def stream_media(identity: str, db: DB, t: str = Query(default="")):
    """Private media streaming gated by a signed, expiring ticket."""
    identity = str(identity or "").strip()
    if identity.startswith("node-"):
        node = db.get(Node, identity[len("node-") :])
        if not node:
            raise HTTPException(404, "Media not found")
        job = db.get(Job, node.job_id)
        owner = job.owner if job else ""
        if not verify_media_ticket(identity, owner, t):
            raise HTTPException(403, "INVALID_OR_EXPIRED_TICKET")
        if not node.output or not media.valid_artifact(node.output):
            raise HTTPException(409, "ARTIFACT_NOT_VERIFIED_OR_STALE")
        path = media.safe_path(node.output["storage_key"])
        suffix = path.suffix.lower()
        media_type = "video/mp4" if suffix == ".mp4" else ("application/x-subrip" if suffix == ".srt" else "application/octet-stream")
        return FileResponse(path, media_type=media_type, filename=path.name)
    if identity.startswith("asset-"):
        asset = db.get(Entity, identity[len("asset-") :])
        if not asset or asset.kind != "asset":
            raise HTTPException(404, "Media not found")
        if not verify_media_ticket(identity, asset.owner, t):
            raise HTTPException(403, "INVALID_OR_EXPIRED_TICKET")
        if not media.valid_artifact(asset.data or {}):
            raise HTTPException(409, "ARTIFACT_NOT_VERIFIED_OR_STALE")
        path = media.safe_path(asset.data["storage_key"])
        return FileResponse(path, filename=path.name)
    raise HTTPException(404, "Media not found")
