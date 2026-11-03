from __future__ import annotations

import hashlib
import json
import os
import re
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings

_VERSION_FILE_RE = re.compile(r"^(?P<key>.+)__v(?P<version>\d+)\.json$")
_LOCK_FILE_NAME = ".template_versions.lock"
_DEFAULT_STORAGE_DIR = "./storage/template_versions"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_tags(tags: Any) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        source = [item.strip() for item in tags.split(",")]
    elif isinstance(tags, list):
        source = [str(item).strip() for item in tags]
    else:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in source:
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    return normalized


def _normalize_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _normalize_template_key(raw_key: Any, *, fallback_name: str = "template") -> str:
    source = _normalize_text(raw_key) or fallback_name
    ascii_text = (
        unicodedata.normalize("NFKD", source)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    if slug:
        return slug[:64]
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]
    return f"tpl-{digest}"


def _resolve_storage_dir(storage_dir: str | Path | None = None) -> Path:
    settings = get_settings()
    configured = _normalize_text(storage_dir)
    if not configured:
        configured = _normalize_text(getattr(settings, "VIDEO_FACTORY_TEMPLATE_STORAGE_DIR", ""))
    if not configured:
        configured = _DEFAULT_STORAGE_DIR
    path = Path(configured).expanduser()
    if not path.is_absolute():
        # backend directory
        base_dir = Path(__file__).resolve().parents[2]
        path = (base_dir / path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _version_file_path(storage_dir: Path, template_key: str, version: int) -> Path:
    return storage_dir / f"{template_key}__v{version:04d}.json"


def _parse_version_file(path: Path) -> tuple[str, int] | None:
    matched = _VERSION_FILE_RE.match(path.name)
    if not matched:
        return None
    return matched.group("key"), int(matched.group("version"))


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temp_path = path.with_name(f"{path.name}.tmp.{uuid.uuid4().hex}")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp_path, path)


class _FileLock:
    """Minimal cross-process lock based on exclusive lock file creation."""

    def __init__(self, lock_path: Path, *, timeout_seconds: float = 8.0, poll_seconds: float = 0.05) -> None:
        self.lock_path = lock_path
        self.timeout_seconds = timeout_seconds
        self.poll_seconds = poll_seconds
        self._fd: int | None = None

    def __enter__(self) -> "_FileLock":
        deadline = time.monotonic() + max(0.2, self.timeout_seconds)
        while True:
            try:
                self._fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(self._fd, str(os.getpid()).encode("utf-8"))
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Template storage lock timeout: {self.lock_path}") from None
                time.sleep(self.poll_seconds)

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self.lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def _record_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("id"),
        "template_key": record.get("template_key"),
        "version": int(record.get("version") or 0),
        "name": record.get("name"),
        "description": record.get("description"),
        "tags": list(record.get("tags") or []),
        "created_at": record.get("created_at"),
        "created_by": record.get("created_by"),
    }


class TemplateVersionStore:
    def __init__(self, storage_dir: str | Path | None = None) -> None:
        self.storage_dir = _resolve_storage_dir(storage_dir)
        self.lock_path = self.storage_dir / _LOCK_FILE_NAME

    def _all_version_files(self, template_key: str | None = None) -> list[Path]:
        if template_key:
            normalized = _normalize_template_key(template_key)
            return sorted(self.storage_dir.glob(f"{normalized}__v*.json"))
        return sorted(self.storage_dir.glob("*__v*.json"))

    def _next_version_locked(self, template_key: str) -> int:
        current_max = 0
        for file_path in self._all_version_files(template_key):
            parsed = _parse_version_file(file_path)
            if parsed and parsed[0] == template_key:
                current_max = max(current_max, parsed[1])
        return current_max + 1

    def list(
        self,
        *,
        template_key: str | None = None,
        latest_only: bool = False,
        with_content: bool = False,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for file_path in self._all_version_files(template_key):
            record = _load_json(file_path)
            if not record:
                continue
            records.append(record)

        records.sort(key=lambda item: (str(item.get("template_key") or ""), int(item.get("version") or 0)), reverse=True)
        if latest_only:
            latest_map: dict[str, dict[str, Any]] = {}
            for item in records:
                key = str(item.get("template_key") or "")
                if key and key not in latest_map:
                    latest_map[key] = item
            records = list(latest_map.values())
            records.sort(key=lambda item: str(item.get("template_key") or ""))

        if with_content:
            return records
        return [_record_summary(item) for item in records]

    def create(self, payload: dict[str, Any], *, created_by: str = "system") -> dict[str, Any]:
        name = _normalize_text(payload.get("name")) or "未命名模板"
        template_key = _normalize_template_key(payload.get("template_key") or payload.get("templateKey") or name, fallback_name=name)
        description = _normalize_text(payload.get("description"))
        tags = _normalize_tags(payload.get("tags"))
        storyboard = _normalize_dict(payload.get("storyboard"))
        keyframe = _normalize_dict(payload.get("keyframe"))
        veo = _normalize_dict(payload.get("veo"))
        created_by_text = _normalize_text(created_by or payload.get("created_by") or payload.get("createdBy")) or "system"

        with _FileLock(self.lock_path):
            version = self._next_version_locked(template_key)
            record = {
                "id": f"{template_key}-v{version}-{uuid.uuid4().hex[:8]}",
                "template_key": template_key,
                "version": version,
                "name": name,
                "description": description,
                "tags": tags,
                "storyboard": storyboard,
                "keyframe": keyframe,
                "veo": veo,
                "created_at": _utc_now_iso(),
                "created_by": created_by_text,
            }
            _atomic_write_json(_version_file_path(self.storage_dir, template_key, version), record)
        return record

    def get(
        self,
        *,
        template_key: str | None = None,
        version: int | None = None,
        template_id: str | None = None,
    ) -> dict[str, Any] | None:
        if template_id:
            target_id = _normalize_text(template_id)
            for file_path in self._all_version_files():
                record = _load_json(file_path)
                if record and str(record.get("id")) == target_id:
                    return record
            return None

        if not template_key:
            return None
        normalized_key = _normalize_template_key(template_key)
        if version is not None:
            return _load_json(_version_file_path(self.storage_dir, normalized_key, int(version)))

        latest_record: dict[str, Any] | None = None
        latest_version = -1
        for file_path in self._all_version_files(normalized_key):
            parsed = _parse_version_file(file_path)
            if not parsed or parsed[0] != normalized_key:
                continue
            if parsed[1] <= latest_version:
                continue
            loaded = _load_json(file_path)
            if loaded:
                latest_version = parsed[1]
                latest_record = loaded
        return latest_record

    def delete(
        self,
        *,
        template_key: str | None = None,
        version: int | None = None,
        template_id: str | None = None,
    ) -> bool:
        with _FileLock(self.lock_path):
            if template_id:
                target_id = _normalize_text(template_id)
                for file_path in self._all_version_files():
                    record = _load_json(file_path)
                    if record and str(record.get("id")) == target_id:
                        file_path.unlink(missing_ok=True)
                        return True
                return False

            if not template_key:
                return False
            normalized_key = _normalize_template_key(template_key)
            if version is not None:
                target_path = _version_file_path(self.storage_dir, normalized_key, int(version))
                if target_path.exists():
                    target_path.unlink(missing_ok=True)
                    return True
                return False

            deleted = False
            for file_path in self._all_version_files(normalized_key):
                file_path.unlink(missing_ok=True)
                deleted = True
            return deleted


_default_store = TemplateVersionStore()


def list_template_versions(
    *,
    template_key: str | None = None,
    latest_only: bool = False,
    with_content: bool = False,
) -> list[dict[str, Any]]:
    return _default_store.list(template_key=template_key, latest_only=latest_only, with_content=with_content)


def create_template_version(payload: dict[str, Any], *, created_by: str = "system") -> dict[str, Any]:
    return _default_store.create(payload, created_by=created_by)


def get_template_version(
    *,
    template_key: str | None = None,
    version: int | None = None,
    template_id: str | None = None,
) -> dict[str, Any] | None:
    return _default_store.get(template_key=template_key, version=version, template_id=template_id)


def delete_template_version(
    *,
    template_key: str | None = None,
    version: int | None = None,
    template_id: str | None = None,
) -> bool:
    return _default_store.delete(template_key=template_key, version=version, template_id=template_id)
