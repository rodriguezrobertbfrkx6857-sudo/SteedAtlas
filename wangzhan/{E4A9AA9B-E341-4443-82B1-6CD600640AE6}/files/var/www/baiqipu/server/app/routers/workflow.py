from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
import httpx
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.models.workflow_task import WorkflowTask
from app.schemas.workflow import (
    WorkflowTaskCallbackIn,
    WorkflowTaskCreateIn,
    WorkflowTaskDispatchIn,
    WorkflowTaskDispatchOut,
    WorkflowTaskListOut,
    WorkflowTaskOut,
)
from app.services.auth import get_current_user
from app.services.workflow_tasks import (
    build_initial_node_states,
    build_standard_input_payload,
    dispatch_workflow_task,
    generate_callback_token,
    generate_workflow_task_id,
    merge_node_states,
    normalize_n8n_webhook_url,
    normalize_workflow_definition,
    run_site_workflow_task,
    serialize_workflow_task,
    derive_status_from_nodes,
)
from app.services.video_factory_providers import list_video_factory_models, video_factory_provider_status
from app.services.workflow_runtime import (
    delete_workflow_runtime,
    read_workflow_runtime,
    sync_task_runtime,
    workflow_runtime_status,
)

router = APIRouter(prefix="/video/workflow", tags=["workflow"])
settings = get_settings()
server_dir = Path(__file__).resolve().parents[2]
generated_dir = server_dir / "generated"
reference_media_dir = generated_dir / "reference-media"


class WorkflowTaskClearIn(BaseModel):
    clear_files: bool = True


def _get_task_for_user(db: Session, task_id: str, user_id: str) -> WorkflowTask:
    task = db.query(WorkflowTask).filter(WorkflowTask.id == task_id, WorkflowTask.user_id == user_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Workflow task not found")
    return task


def _is_real_video_url(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text) and not text.startswith("pending://") and not text.startswith("mock://")


def _first_video_url_from_output(output: dict[str, object]) -> str:
    for key in ("videoUrl", "firstVideoUrl"):
        video_url = str(output.get(key) or "").strip()
        if _is_real_video_url(video_url):
            return video_url

    source_clips = output.get("sourceClips")
    if isinstance(source_clips, list):
        for clip_url in source_clips:
            video_url = str(clip_url or "").strip()
            if _is_real_video_url(video_url):
                return video_url

    clips = output.get("clips")
    if isinstance(clips, list):
        for clip in clips:
            if not isinstance(clip, dict):
                continue
            for key in ("url", "videoUrl"):
                video_url = str(clip.get(key) or "").strip()
                if _is_real_video_url(video_url):
                    return video_url
    return ""


def _task_video_url(task: WorkflowTask) -> str:
    result_payload = task.result_payload if isinstance(task.result_payload, dict) else {}
    video_url = _first_video_url_from_output(result_payload)
    if video_url:
        return video_url
    for state in task.node_states or []:
        if not isinstance(state, dict):
            continue
        output = state.get("output") if isinstance(state.get("output"), dict) else {}
        video_url = _first_video_url_from_output(output)
        if video_url:
            return video_url
    return ""


def _download_filename(task: WorkflowTask) -> str:
    safe_title = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in task.title)[:48].strip("_")
    return f"{safe_title or task.id}_{task.id}.mp4"


def _iter_remote_video(url: str):
    from app.v2.security import public_url
    public_url(url)  # Empty allowlist by default; no arbitrary remote proxy.
    with httpx.stream("GET", url, timeout=300.0, follow_redirects=False) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes(chunk_size=1024 * 1024):
            if chunk:
                yield chunk


def _safe_reference_suffix(filename: str, content_type: str) -> tuple[str, str]:
    suffix = Path(str(filename or "")).suffix.lower()
    image_suffixes = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
    video_suffixes = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
    if suffix in image_suffixes:
        return suffix, "image"
    if suffix in video_suffixes:
        return suffix, "video"
    lowered_type = str(content_type or "").lower()
    if lowered_type.startswith("image/"):
        return ".jpg", "image"
    if lowered_type.startswith("video/"):
        return ".mp4", "video"
    raise HTTPException(status_code=400, detail="Unsupported reference file type. Please upload image or video.")


def _safe_reference_name(filename: str) -> str:
    stem = Path(str(filename or "reference")).stem
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", stem).strip("_")
    return cleaned or "reference"


def _cleanup_generated_files_for_task(task_id: str) -> list[str]:
    safe_prefix = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in task_id)
    if not safe_prefix:
        return []
    removed: list[str] = []
    root = generated_dir.resolve()
    for child in generated_dir.rglob(f"{safe_prefix}*"):
        if not child.is_file():
            continue
        resolved = child.resolve()
        if not str(resolved).startswith(str(root)):
            continue
        try:
            child.unlink()
            removed.append(str(resolved.relative_to(root)))
        except OSError:
            continue
    return removed


def _delete_task_record(task: WorkflowTask) -> list[str]:
    removed_files = _cleanup_generated_files_for_task(task.id)
    delete_workflow_runtime(task.id)
    return removed_files


@router.get("/provider-status")
def get_video_factory_provider_status(user: User = Depends(get_current_user)):
    return {
        **video_factory_provider_status(),
        "runtime": workflow_runtime_status(),
    }


@router.get("/provider-models")
def get_video_factory_provider_models(user: User = Depends(get_current_user)):
    return list_video_factory_models()


@router.get("/runtime-status")
def get_workflow_runtime_status(user: User = Depends(get_current_user)):
    return workflow_runtime_status()


@router.post("/reference/upload")
async def upload_reference_media(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    suffix, media_type = _safe_reference_suffix(file.filename or "", file.content_type or "")
    max_bytes = max(1, int(settings.VIDEO_FACTORY_REFERENCE_MAX_UPLOAD_MB or 256)) * 1024 * 1024
    reference_media_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = _safe_reference_name(file.filename or "reference")
    target = reference_media_dir / f"ref_{timestamp}_{uuid.uuid4().hex[:8]}_{safe_name}{suffix}"

    total_bytes = 0
    try:
        try:
            with target.open("wb") as out_file:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail=f"Reference file too large. Max {settings.VIDEO_FACTORY_REFERENCE_MAX_UPLOAD_MB}MB.",
                        )
                    out_file.write(chunk)
        except Exception:
            try:
                if target.exists():
                    target.unlink()
            except OSError:
                pass
            raise
    finally:
        await file.close()

    if total_bytes <= 0:
        try:
            target.unlink()
        except OSError:
            pass
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=500, detail="Failed to save uploaded reference file.")

    relative = target.resolve().relative_to(generated_dir.resolve()).as_posix()
    return {
        "status": "uploaded",
        "mediaType": media_type,
        "fileName": target.name,
        "contentType": file.content_type or "",
        "sizeBytes": total_bytes,
        "mediaUrl": f"/generated/{relative}",
        "localPath": str(target.resolve()),
        "message": "Reference media uploaded successfully.",
    }


@router.get("/tasks/{task_id}/runtime")
def get_workflow_task_runtime(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_task_for_user(db, task_id, user.id)
    return read_workflow_runtime(task_id) or {"taskId": task_id, "status": "unavailable"}


@router.get("/tasks/{task_id}/download")
def download_workflow_task_video(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = _get_task_for_user(db, task_id, user.id)
    video_url = _task_video_url(task)
    if not video_url or video_url.startswith("pending://"):
        raise HTTPException(status_code=409, detail="Video is not ready for download")

    filename = _download_filename(task)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if video_url.startswith("/generated/"):
        relative = video_url.removeprefix("/generated/").lstrip("/\\")
        file_path = (generated_dir / relative).resolve()
        if not str(file_path).startswith(str(generated_dir.resolve())) or not file_path.exists():
            raise HTTPException(status_code=404, detail="Generated video file not found")
        return FileResponse(file_path, media_type="video/mp4", filename=filename)

    parsed = urlparse(video_url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Unsupported video URL")
    return StreamingResponse(_iter_remote_video(video_url), media_type="video/mp4", headers=headers)


@router.post("/tasks", response_model=WorkflowTaskDispatchOut)
def create_workflow_task(
    req: WorkflowTaskCreateIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workflow_definition = normalize_workflow_definition(req.workflow_definition)
    horse_name = req.horse_name or str(req.input_payload.get("horse") or req.input_payload.get("horse_name") or "").strip() or None
    webhook_url = normalize_n8n_webhook_url(req.webhook_url) if req.webhook_url else None

    task = WorkflowTask(
        id=generate_workflow_task_id(),
        user_id=user.id,
        title=req.title.strip(),
        horse_name=horse_name,
        status="draft",
        progress=0,
        current_node="input",
        aspect_ratio=req.aspect_ratio.strip(),
        duration=req.duration,
        webhook_url=webhook_url,
        callback_token=generate_callback_token(),
        workflow_definition=workflow_definition,
        input_payload=dict(req.input_payload or {}),
        normalized_payload={},
        node_states=build_initial_node_states(workflow_definition),
        result_payload={},
        dispatch_response={},
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    task.normalized_payload = build_standard_input_payload(task)
    db.add(task)
    db.commit()
    db.refresh(task)
    sync_task_runtime(task, event="task-created", event_payload={"autoStart": req.auto_start})

    dispatch_status = "created"
    message = "Workflow task created"
    effective_webhook_url = normalize_n8n_webhook_url(webhook_url) if webhook_url else ""
    if req.auto_start and effective_webhook_url:
        dispatch_status = "queued"
        message = "Workflow task created and queued for n8n dispatch"
        background_tasks.add_task(dispatch_workflow_task, task.id)
    elif req.auto_start:
        dispatch_status = "queued"
        message = "Workflow task created and queued for site workflow"
        background_tasks.add_task(run_site_workflow_task, task.id)

    return WorkflowTaskDispatchOut(
        task=WorkflowTaskOut(**serialize_workflow_task(task)),
        dispatch_status=dispatch_status,
        message=message,
    )


@router.post("/tasks/{task_id}/run", response_model=WorkflowTaskDispatchOut)
def run_existing_workflow_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = _get_task_for_user(db, task_id, user.id)
    task.node_states = build_initial_node_states(task.workflow_definition)
    task.status = "queued"
    task.progress = 4
    task.current_node = "input"
    task.error_message = None
    task.dispatch_response = {
        "execution_mode": "site-workflow",
        "message": "Workflow is running inside Baiqipu backend",
    }
    task.result_payload = {}
    task.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(task)
    db.commit()
    db.refresh(task)
    sync_task_runtime(task, event="workflow-queued", event_payload={"mode": "site-workflow"})
    background_tasks.add_task(run_site_workflow_task, task.id)
    return WorkflowTaskDispatchOut(
        task=WorkflowTaskOut(**serialize_workflow_task(task)),
        dispatch_status="queued",
        message="Workflow task queued for site workflow",
    )


@router.post("/tasks/{task_id}/clear")
def clear_workflow_task(
    task_id: str,
    req: WorkflowTaskClearIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = _get_task_for_user(db, task_id, user.id)
    removed_files = _cleanup_generated_files_for_task(task.id) if (req is None or req.clear_files) else []
    task.status = "cancelled"
    task.progress = 100
    task.current_node = task.current_node or "input"
    task.error_message = "工作流已由用户清空状态并取消。"
    task.node_states = merge_node_states(
        task.node_states,
        node_id=task.current_node,
        node_status="cancelled",
        node_progress=100,
        node_output={"cancelled": True, "removedFiles": removed_files},
    )
    task.result_payload = {}
    next_dispatch = dict(task.dispatch_response or {})
    next_dispatch.update(
        {
            "clear_status": "cancelled",
            "removed_files": removed_files,
            "remote_note": "已提交到外部 Veo 的任务无法由本站保证撤回；本站会停止等待和回写。",
        }
    )
    task.dispatch_response = next_dispatch
    task.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(task)
    db.commit()
    db.refresh(task)
    sync_task_runtime(task, event="workflow-cleared", event_payload={"removedFiles": removed_files})
    return {
        "task": serialize_workflow_task(task),
        "status": "cancelled",
        "removed_files": removed_files,
        "message": "当前工作流已取消，本地生成文件已清理。" if removed_files else "当前工作流已取消。",
    }


@router.post("/tasks/{task_id}/dispatch", response_model=WorkflowTaskDispatchOut)
def dispatch_existing_workflow_task(
    task_id: str,
    req: WorkflowTaskDispatchIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = _get_task_for_user(db, task_id, user.id)
    if req and req.webhook_url:
        task.webhook_url = normalize_n8n_webhook_url(req.webhook_url) or None
        task.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(task)
        db.commit()
        db.refresh(task)

    dispatch_result = dispatch_workflow_task(task.id)
    db.refresh(task)
    return WorkflowTaskDispatchOut(
        task=WorkflowTaskOut(**serialize_workflow_task(task)),
        dispatch_status=str(dispatch_result.get("dispatch_status") or "unknown"),
        message=str(dispatch_result.get("message") or "Dispatch finished"),
    )


@router.get("/tasks/{task_id}", response_model=WorkflowTaskOut)
def get_workflow_task(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = _get_task_for_user(db, task_id, user.id)
    return WorkflowTaskOut(**serialize_workflow_task(task))


@router.get("/tasks", response_model=WorkflowTaskListOut)
def list_workflow_tasks(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tasks = (
        db.query(WorkflowTask)
        .filter(WorkflowTask.user_id == user.id)
        .order_by(WorkflowTask.created_at.desc(), WorkflowTask.id.desc())
        .limit(limit)
        .all()
    )
    return WorkflowTaskListOut(items=[WorkflowTaskOut(**serialize_workflow_task(task)) for task in tasks])


@router.delete("/tasks/{task_id}")
def delete_workflow_task(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = _get_task_for_user(db, task_id, user.id)
    removed_files = _delete_task_record(task)
    db.delete(task)
    db.commit()
    return {
        "status": "deleted",
        "task_id": task_id,
        "removed_files": removed_files,
        "message": "任务历史已删除，相关本地生成文件已清理。",
    }


@router.delete("/tasks")
def delete_all_workflow_tasks(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    user_tasks = db.query(WorkflowTask).filter(WorkflowTask.user_id == user.id).all()
    removed_files: list[str] = []
    task_ids: list[str] = []
    for task in user_tasks:
        task_ids.append(task.id)
        removed_files.extend(_delete_task_record(task))
        db.delete(task)
    db.commit()
    return {
        "status": "deleted",
        "deleted_count": len(task_ids),
        "task_ids": task_ids,
        "removed_files": removed_files,
        "message": "全部任务历史已删除，相关本地生成文件已清理。",
    }


@router.post("/callback/{task_id}", response_model=WorkflowTaskOut)
def receive_workflow_callback(
    task_id: str,
    req: WorkflowTaskCallbackIn,
    db: Session = Depends(get_db),
    callback_token_header: str | None = Header(default=None, alias="X-Workflow-Task-Token"),
    callback_secret_header: str | None = Header(default=None, alias="X-Workflow-Callback-Secret"),
    callback_token_query: str | None = Query(default=None, alias="token"),
):
    task = db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Workflow task not found")

    callback_token = (callback_token_header or callback_token_query or req.callback_token or "").strip()
    shared_secret = str(callback_secret_header or "").strip()
    expected_secret = str(settings.N8N_CALLBACK_SHARED_SECRET or "").strip()
    token_valid = callback_token and callback_token == task.callback_token
    secret_valid = expected_secret and shared_secret == expected_secret
    if not token_valid and not secret_valid:
        raise HTTPException(status_code=403, detail="Invalid workflow callback credentials")

    node_states = merge_node_states(
        task.node_states,
        incoming_states=[state.model_dump() for state in req.node_states],
        node_id=req.node_id,
        node_status=req.node_status,
        node_progress=req.node_progress,
        node_output=req.node_output,
    )

    task.node_states = node_states
    if req.normalized_payload:
        next_payload = dict(task.normalized_payload or {})
        next_payload.update(req.normalized_payload)
        task.normalized_payload = next_payload
    if req.result_payload:
        next_result = dict(task.result_payload or {})
        next_result.update(req.result_payload)
        task.result_payload = next_result
    if req.dispatch_response:
        next_dispatch = dict(task.dispatch_response or {})
        next_dispatch.update(req.dispatch_response)
        task.dispatch_response = next_dispatch
    if req.n8n_execution_id:
        task.n8n_execution_id = req.n8n_execution_id.strip()
    if req.current_node:
        task.current_node = req.current_node.strip()
    elif req.node_id:
        task.current_node = req.node_id.strip()
    if req.error_message is not None:
        task.error_message = req.error_message
    if req.progress is not None:
        task.progress = req.progress
    else:
        task.progress = max(int(item.get("progress") or 0) for item in node_states) if node_states else task.progress
    if req.status:
        task.status = req.status
    else:
        task.status = derive_status_from_nodes(node_states)
    task.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(task)
    db.commit()
    db.refresh(task)
    sync_task_runtime(
        task,
        event=req.event or "callback",
        event_payload={"nodeId": req.node_id, "status": task.status, "progress": task.progress},
    )
    return WorkflowTaskOut(**serialize_workflow_task(task))
