"""End-to-end check of the V2-backed video factory compatibility adapter.

Creates a task through the original frontend contract, waits for the CPU worker,
then verifies MP4/SRT download and signed media ticket access.
"""

import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(
    ROOT, "wangzhan", "{E4A9AA9B-E341-4443-82B1-6CD600640AE6}", "files", "var", "www", "baiqipu", "server"
)
sys.path.insert(0, SERVER)

os.environ.update(
    DATABASE_URL="sqlite:///" + os.path.join(ROOT, "runtime", "compat-e2e.db").replace("\\", "/"),
    DEBUG="false",
    SECRET_KEY="compat-e2e-" + ("b" * 48),
    STEEDATLAS_ROOT=ROOT,
    VIDEO_FACTORY_API_MODE="off",
    WORKFLOW_RUNTIME_REDIS_ENABLED="false",
)

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.auth import create_access_token  # noqa: E402
from app.v2 import runtime as v2runtime  # noqa: E402

BASE = "/api/v2/compat/workflow"


def log(message: str) -> None:
    print(f"[compat-e2e] {message}", flush=True)


def main() -> int:
    db_path = os.environ["DATABASE_URL"].replace("sqlite:///", "")
    if os.path.exists(db_path):
        os.remove(db_path)
    Base.metadata.create_all(engine)

    with SessionLocal() as db:
        db.add(User(id="alice", nickname="alice", role="user"))
        db.commit()

    v2runtime.SessionLocal = SessionLocal
    headers = {"Authorization": "Bearer " + create_access_token("alice")}

    with TestClient(app) as client:
        status = client.get(BASE + "/provider-status", headers=headers)
        assert status.status_code == 200, status.text
        payload = status.json()
        assert payload["gpt"]["configured"] is True
        assert payload["veo"]["external"] is False
        log("provider-status ok: local CPU engine only")

        models = client.get(BASE + "/provider-models", headers=headers)
        assert models.status_code == 200, models.text
        log("provider-models ok: " + ", ".join(models.json()["veo"]["models"][0]["id"] for _ in [0]))

        create = client.post(
            BASE + "/tasks",
            headers=headers,
            json={
                "title": "赤兔马为什么成为忠义象征",
                "horse_name": "赤兔",
                "duration": 18,
                "aspect_ratio": "9:16",
                "workflow_definition": {"name": "baiqipu-video-factory-site-workflow", "nodes": [], "connections": []},
                "input_payload": {
                    "topic": "赤兔马为什么成为忠义象征",
                    "horse": "赤兔",
                    "horse_name": "赤兔",
                    "brief": "强调史料与传说的边界",
                    "aspect_ratio": "9:16",
                    "storyboard": {"shotCount": "3", "shotSeconds": "6"},
                },
                "auto_start": True,
            },
        )
        assert create.status_code == 200, create.text
        task = create.json()["task"]
        task_id = task["task_id"]
        log(f"task created: {task_id} status={task['status']}")

        deadline = time.time() + 300
        final = None
        while time.time() < deadline:
            v2runtime.work_once("e2e-worker")
            response = client.get(BASE + f"/tasks/{task_id}", headers=headers)
            assert response.status_code == 200, response.text
            final = response.json()
            if final["status"] not in {"queued", "processing"}:
                break
            time.sleep(0.4)

        assert final is not None
        assert final["status"] == "completed", json.dumps(final, ensure_ascii=False)[:2000]
        log("task completed: " + final["status"])

        video_url = final["result_payload"].get("videoUrl")
        assert video_url, json.dumps(final["result_payload"], ensure_ascii=False)
        log("video url: " + video_url)

        download = client.get(BASE + f"/tasks/{task_id}/download", headers=headers)
        assert download.status_code == 200, download.text
        assert download.headers["content-type"].startswith("video/"), download.headers
        assert len(download.content) > 5000, len(download.content)
        log(f"download ok: {len(download.content)} bytes, {download.headers.get('content-disposition')}")

        media = client.get(video_url)
        assert media.status_code == 200, media.text
        assert len(media.content) > 5000
        log("signed media ticket ok")

        tampered = client.get(video_url.replace("t=", "t=x"))
        assert tampered.status_code == 403, tampered.status_code
        log("tampered ticket rejected with 403")

        other = client.get(video_url)
        assert other.status_code == 200

        srt_url = final["result_payload"].get("srtUrl")
        assert srt_url, json.dumps(final["result_payload"], ensure_ascii=False)
        srt = client.get(srt_url)
        assert srt.status_code == 200, srt.text
        assert "-->" in srt.text
        log("srt ok: " + str(len(srt.text)) + " chars")

        listing = client.get(BASE + "/tasks?limit=5", headers=headers)
        assert listing.status_code == 200, listing.text
        assert any(item["task_id"] == task_id for item in listing.json()["items"])
        log("task list ok")

        runtime_view = client.get(BASE + f"/tasks/{task_id}/runtime", headers=headers)
        assert runtime_view.status_code == 200, runtime_view.text
        log("runtime ok: " + runtime_view.json()["status"])

        rerun = client.post(BASE + f"/tasks/{task_id}/run", headers=headers)
        assert rerun.status_code == 200, rerun.text
        log("re-run queued ok")

        cleared = client.post(BASE + f"/tasks/{task_id}/clear", headers=headers)
        assert cleared.status_code == 200, cleared.text
        log("clear ok")

        removed = client.delete(BASE + f"/tasks/{task_id}", headers=headers)
        assert removed.status_code == 200, removed.text
        log("delete ok")

        forbidden = client.get(BASE + f"/tasks/{task_id}", headers=headers)
        assert forbidden.status_code == 404, forbidden.status_code
        log("deleted task returns 404")

    log("ALL COMPAT E2E CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
