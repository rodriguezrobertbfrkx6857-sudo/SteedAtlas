from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import redis
from redis.exceptions import RedisError

from app.config import get_settings

settings = get_settings()
_redis_client: redis.Redis | None = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _safe_json_loads(value: str | bytes | None, fallback: Any) -> Any:
    if value is None:
        return fallback
    try:
        text = value.decode("utf-8") if isinstance(value, bytes) else value
        return json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return fallback


def get_workflow_runtime_redis() -> redis.Redis | None:
    global _redis_client
    if not settings.WORKFLOW_RUNTIME_REDIS_ENABLED:
        return None
    if _redis_client is not None:
        try:
            _redis_client.ping()
            return _redis_client
        except RedisError:
            _redis_client = None
    redis_url = str(settings.REDIS_URL or "").strip()
    if not redis_url:
        return None
    try:
        client = redis.Redis.from_url(redis_url, decode_responses=False, socket_timeout=2.0, socket_connect_timeout=2.0)
        client.ping()
        _redis_client = client
        return client
    except RedisError:
        return None


def workflow_runtime_status() -> dict[str, Any]:
    client = get_workflow_runtime_redis()
    return {
        "enabled": bool(settings.WORKFLOW_RUNTIME_REDIS_ENABLED),
        "connected": bool(client),
        "prefix": settings.WORKFLOW_RUNTIME_REDIS_PREFIX,
        "ttlSeconds": settings.WORKFLOW_RUNTIME_REDIS_TTL_SECONDS,
        "eventLimit": settings.WORKFLOW_RUNTIME_REDIS_EVENT_LIMIT,
    }


def _task_key(task_id: str) -> str:
    return f"{settings.WORKFLOW_RUNTIME_REDIS_PREFIX}{task_id}"


def read_workflow_runtime(task_id: str) -> dict[str, Any] | None:
    client = get_workflow_runtime_redis()
    if not client:
        return None
    try:
        data = client.get(_task_key(task_id))
    except RedisError:
        return None
    parsed = _safe_json_loads(data, None)
    return parsed if isinstance(parsed, dict) else None


def write_workflow_runtime(task_id: str, payload: dict[str, Any]) -> None:
    client = get_workflow_runtime_redis()
    if not client:
        return
    try:
        client.setex(_task_key(task_id), max(60, int(settings.WORKFLOW_RUNTIME_REDIS_TTL_SECONDS)), _safe_json_dumps(payload))
    except RedisError:
        return


def delete_workflow_runtime(task_id: str) -> None:
    client = get_workflow_runtime_redis()
    if not client:
        return
    try:
        client.delete(_task_key(task_id))
    except RedisError:
        return


def task_runtime_payload(task: Any, *, event: str | None = None, event_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    previous = read_workflow_runtime(str(task.id)) or {}
    events = previous.get("events") if isinstance(previous.get("events"), list) else []
    next_events = list(events)
    if event:
        next_events.append(
            {
                "event": event,
                "at": _utc_now_iso(),
                "status": getattr(task, "status", None),
                "progress": getattr(task, "progress", None),
                "currentNode": getattr(task, "current_node", None),
                "payload": event_payload or {},
            }
        )
    limit = max(10, int(settings.WORKFLOW_RUNTIME_REDIS_EVENT_LIMIT or 120))
    node_states = getattr(task, "node_states", None)
    result_payload = getattr(task, "result_payload", None)
    dispatch_response = getattr(task, "dispatch_response", None)
    active_nodes = [
        str(item.get("node_id"))
        for item in (node_states or [])
        if isinstance(item, dict) and str(item.get("status") or "").lower() in {"processing", "running"}
    ]
    return {
        "taskId": str(task.id),
        "title": getattr(task, "title", ""),
        "status": getattr(task, "status", None),
        "progress": int(getattr(task, "progress", 0) or 0),
        "currentNode": getattr(task, "current_node", None),
        "activeNodes": active_nodes,
        "nodeStates": list(node_states or []),
        "resultPayload": dict(result_payload or {}) if isinstance(result_payload, dict) else {},
        "dispatchResponse": dict(dispatch_response or {}) if isinstance(dispatch_response, dict) else {},
        "errorMessage": getattr(task, "error_message", None),
        "updatedAt": _utc_now_iso(),
        "events": next_events[-limit:],
    }


def sync_task_runtime(task: Any, *, event: str | None = None, event_payload: dict[str, Any] | None = None) -> None:
    write_workflow_runtime(str(task.id), task_runtime_payload(task, event=event, event_payload=event_payload))
