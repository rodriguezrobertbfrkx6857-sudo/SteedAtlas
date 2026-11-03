"""Audit legacy `/generated/*` asset ownership.

The original site stored generated media under `server/generated/` with no
per-file ownership metadata. This script reports what actually exists on disk
versus what the legacy `workflow_tasks` table claims, so an audited claiming
endpoint can be designed on evidence rather than assumptions.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "wangzhan/{E4A9AA9B-E341-4443-82B1-6CD600640AE6}/files/var/www/baiqipu/server"
GENERATED = SERVER / "generated"


def audit_generated_dir():
    files = []
    if GENERATED.is_dir():
        for path in GENERATED.rglob("*"):
            if path.is_file():
                files.append(
                    {
                        "relative": path.relative_to(GENERATED).as_posix(),
                        "bytes": path.stat().st_size,
                    }
                )
    return files


def audit_legacy_tasks(db_path):
    if not db_path.exists():
        return {"database": str(db_path), "exists": False, "tasks": []}
    db = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
    rows = list(
        db.execute(
            "select id, user_id, status, result_payload from workflow_tasks"
        )
    )
    db.close()
    tasks = []
    for task_id, user_id, status, payload in rows:
        try:
            parsed = json.loads(payload or "{}")
        except json.JSONDecodeError:
            parsed = {}
        urls = []
        for key in ("videoUrl", "subtitleUrl", "coverUrl", "firstVideoUrl", "sourceVideoUrl"):
            value = str(parsed.get(key) or "")
            if value.startswith("/generated/"):
                urls.append(value)
        clips = parsed.get("sourceClips")
        if isinstance(clips, list):
            for clip in clips:
                value = str(clip or "")
                if value.startswith("/generated/"):
                    urls.append(value)
        if urls:
            tasks.append(
                {
                    "task_id": task_id,
                    "user_id": user_id,
                    "status": status,
                    "generated_urls": sorted(set(urls)),
                }
            )
    return {"database": str(db_path), "exists": True, "tasks": tasks}


def main() -> int:
    db_path = ROOT / "runtime/steedatlas.db"
    files = audit_generated_dir()
    legacy = audit_legacy_tasks(db_path)
    claimed_paths = set()
    for task in legacy["tasks"]:
        for url in task["generated_urls"]:
            claimed_paths.add(url.removeprefix("/generated/"))
    on_disk = {item["relative"] for item in files}
    report = {
        "generated_dir": str(GENERATED),
        "files_on_disk": len(files),
        "legacy_tasks_with_generated_urls": len(legacy["tasks"]),
        "distinct_claimed_paths": len(claimed_paths),
        "claimed_paths_present_on_disk": sorted(claimed_paths & on_disk),
        "disk_files_without_claim": sorted(on_disk - claimed_paths)[:50],
        "disk_files_without_claim_count": len(on_disk - claimed_paths),
        "claimable": bool(claimed_paths & on_disk),
        "verdict": (
            "Ownership can be derived from workflow_tasks.user_id for the files that still exist."
            if claimed_paths & on_disk
            else "No legacy generated file is present on disk; nothing is claimable."
        ),
    }
    out = ROOT / "reports/legacy-asset-ownership.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
