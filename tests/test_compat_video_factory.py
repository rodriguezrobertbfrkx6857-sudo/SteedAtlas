"""Tests for the V2-backed video factory compatibility adapter and legacy assets."""

import time

from app.v2 import runtime
from app.v2.models import Entity, Job, Node
from sqlalchemy import select

COMPAT = "/api/v2/compat/workflow"


def _drain(limit=60):
    """Run the CPU worker until no work is left."""
    for _ in range(limit):
        if not runtime.work_once("pytest-worker"):
            return
        time.sleep(0.05)


def _create_task(client, headers, **overrides):
    payload = {
        "title": "赤兔马为什么成为忠义象征",
        "horse_name": "赤兔",
        "duration": 18,
        "aspect_ratio": "9:16",
        "workflow_definition": {"name": "baiqipu-video-factory-site-workflow", "nodes": [], "connections": []},
        "input_payload": {
            "topic": "赤兔马为什么成为忠义象征",
            "horse": "赤兔",
            "horse_name": "赤兔",
            "brief": "区分史料与传说",
            "aspect_ratio": "9:16",
            "storyboard": {"shotCount": "2", "shotSeconds": "2"},
        },
        "auto_start": True,
    }
    payload.update(overrides)
    response = client.post(COMPAT + "/tasks", headers=headers["alice"], json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_provider_status_reports_local_cpu_only(system):
    c, f, h = system
    response = c.get(COMPAT + "/provider-status", headers=h["alice"])
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "v2-local-cpu"
    assert payload["veo"]["external"] is False
    assert payload["gpt"]["external"] is False
    assert payload["xhs"]["enabled"] is False


def test_provider_models_are_local(system):
    c, f, h = system
    payload = c.get(COMPAT + "/provider-models", headers=h["alice"]).json()
    assert payload["veo"]["models"][0]["id"] == "steedatlas-cpu-ffmpeg"
    assert payload["gpt"]["models"][0]["source"] == "local"


def test_task_requires_authentication(system):
    c, f, h = system
    assert c.get(COMPAT + "/provider-status").status_code == 401
    assert c.post(COMPAT + "/tasks", json={"title": "x"}).status_code == 401


def test_task_lifecycle_renders_real_cpu_video(system):
    c, f, h = system
    created = _create_task(c, h)
    task_id = created["task"]["task_id"]
    assert created["dispatch_status"] == "queued"

    _drain()
    final = c.get(COMPAT + f"/tasks/{task_id}", headers=h["alice"]).json()
    assert final["status"] == "completed", final
    assert final["progress"] == 100

    video_url = final["result_payload"]["videoUrl"]
    assert video_url.startswith("/api/v2/compat/workflow/media/node-")
    assert final["result_payload"]["srtUrl"]

    download = c.get(COMPAT + f"/tasks/{task_id}/download", headers=h["alice"])
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("video/")
    assert len(download.content) > 5000

    media = c.get(video_url)
    assert media.status_code == 200
    assert media.headers["content-type"].startswith("video/")
    assert len(media.content) > 5000

    srt = c.get(final["result_payload"]["srtUrl"])
    assert srt.status_code == 200
    assert "-->" in srt.text


def test_signed_ticket_is_required_and_bound(system):
    c, f, h = system
    created = _create_task(c, h)
    task_id = created["task"]["task_id"]
    _drain()
    final = c.get(COMPAT + f"/tasks/{task_id}", headers=h["alice"]).json()
    video_url = final["result_payload"]["videoUrl"]

    tampered = video_url.replace("t=", "t=0.")
    assert c.get(tampered).status_code == 403
    assert c.get("/api/v2/compat/workflow/media/node-unknown?t=1").status_code == 404


def test_tasks_are_scoped_to_their_owner(system):
    c, f, h = system
    created = _create_task(c, h)
    task_id = created["task"]["task_id"]
    assert c.get(COMPAT + f"/tasks/{task_id}", headers=h["bob"]).status_code == 404
    assert c.delete(COMPAT + f"/tasks/{task_id}", headers=h["bob"]).status_code == 404
    listing = c.get(COMPAT + "/tasks", headers=h["bob"]).json()
    assert all(item["task_id"] != task_id for item in listing["items"])


def test_every_job_finishes(system):
    c, f, h = system
    _create_task(c, h)
    _create_task(c, h)
    with f() as db:
        jobs = db.scalars(select(Job)).all()
        assert len(jobs) == 2
    _drain()
    with f() as db:
        statuses = {j.status for j in db.scalars(select(Job)).all()}
    assert statuses == {"SUCCEEDED"}


def test_clear_and_delete_remove_the_task(system):
    c, f, h = system
    created = _create_task(c, h)
    task_id = created["task"]["task_id"]
    _drain()

    cleared = c.post(COMPAT + f"/tasks/{task_id}/clear", headers=h["alice"])
    assert cleared.status_code == 200
    assert cleared.json()["status"] == "cancelled"

    assert c.delete(COMPAT + f"/tasks/{task_id}", headers=h["alice"]).status_code == 200
    assert c.get(COMPAT + f"/tasks/{task_id}", headers=h["alice"]).status_code == 404


def test_delete_all_tasks(system):
    c, f, h = system
    _create_task(c, h)
    _create_task(c, h)
    result = c.delete(COMPAT + "/tasks", headers=h["alice"])
    assert result.status_code == 200
    assert result.json()["deleted_count"] == 2
    assert c.get(COMPAT + "/tasks", headers=h["alice"]).json()["items"] == []


def test_rerun_creates_a_second_job(system):
    c, f, h = system
    created = _create_task(c, h)
    task_id = created["task"]["task_id"]
    _drain()
    assert c.post(COMPAT + f"/tasks/{task_id}/run", headers=h["alice"]).status_code == 200
    _drain()
    with f() as db:
        jobs = db.scalars(select(Job)).all()
        assert len(jobs) == 2
        assert all(j.status == "SUCCEEDED" for j in jobs)


def test_reference_upload_creates_an_owned_asset(system):
    c, f, h = system
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(buffer, format="PNG")
    png = buffer.getvalue()
    response = c.post(
        COMPAT + "/reference/upload",
        headers=h["alice"],
        files={"file": ("ref.png", png, "image/png")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["mediaType"] == "image"
    assert payload["mediaUrl"].startswith("/api/v2/compat/workflow/media/asset-")
    assert c.get(payload["mediaUrl"]).status_code == 200
    with f() as db:
        assets = db.scalars(select(Entity).where(Entity.kind == "asset")).all()
        assert len(assets) == 1
        assert assets[0].owner == "alice"


def test_square_aspect_is_supported(system):
    c, f, h = system
    created = _create_task(c, h, aspect_ratio="1:1")
    task_id = created["task"]["task_id"]
    _drain()
    final = c.get(COMPAT + f"/tasks/{task_id}", headers=h["alice"]).json()
    assert final["status"] == "completed", final
    download = c.get(COMPAT + f"/tasks/{task_id}/download", headers=h["alice"])
    assert download.status_code == 200


def test_legacy_asset_audit_and_claim(system, tmp_path, monkeypatch):
    c, f, h = system
    import app.v2.legacy_assets as legacy

    generated = tmp_path / "generated"
    (generated / "videos").mkdir(parents=True)
    sample = generated / "videos" / "legacy_final.mp4"
    sample.write_bytes(b"\x00" * 32)
    monkeypatch.setattr(legacy, "GENERATED_DIR", generated)

    from app.models.workflow_task import WorkflowTask

    with f() as db:
        db.add(
            WorkflowTask(
                id="wft_legacy1",
                user_id="alice",
                title="旧任务",
                callback_token="tok",
                result_payload={"videoUrl": "/generated/videos/legacy_final.mp4"},
            )
        )
        db.commit()

    audit = c.get("/api/v2/legacy-assets/audit", headers=h["staff"])
    assert audit.status_code == 200
    body = audit.json()
    assert body["files_on_disk"] == 1
    assert "videos/legacy_final.mp4" in body["claimable_paths"]

    other = c.post(
        "/api/v2/legacy-assets/claim",
        headers=h["bob"],
        json={"relative_path": "videos/legacy_final.mp4"},
    )
    assert other.status_code == 403

    claimed = c.post(
        "/api/v2/legacy-assets/claim",
        headers=h["alice"],
        json={"relative_path": "videos/legacy_final.mp4"},
    )
    assert claimed.status_code == 201, claimed.text
    assert claimed.json()["legacy_owner_ids"] == ["alice"]

    again = c.post(
        "/api/v2/legacy-assets/claim",
        headers=h["alice"],
        json={"relative_path": "videos/legacy_final.mp4"},
    )
    assert again.status_code == 409

    orphan = generated / "videos" / "orphan.mp4"
    orphan.write_bytes(b"\x00" * 8)
    refused = c.post(
        "/api/v2/legacy-assets/claim",
        headers=h["alice"],
        json={"relative_path": "videos/orphan.mp4"},
    )
    assert refused.status_code == 409

    traversal = c.post(
        "/api/v2/legacy-assets/claim",
        headers=h["alice"],
        json={"relative_path": "../../etc/passwd"},
    )
    assert traversal.status_code == 422

    inventory = c.get("/api/v2/legacy-assets/inventory", headers=h["alice"])
    assert inventory.status_code == 200
    assert any(item["legacy_relative_path"] == "videos/legacy_final.mp4" for item in inventory.json())


def test_compat_task_is_persisted_as_project_and_job(system):
    c, f, h = system
    created = _create_task(c, h)
    task_id = created["task"]["task_id"]
    with f() as db:
        task = db.get(Entity, task_id)
        assert task is not None
        assert task.kind == "compat_task"
        project = db.get(Entity, task.data["project_id"])
        assert project.kind == "project"
        assert project.data["review_state"] == "APPROVED"
        job = db.get(Job, task.data["job_id"])
        assert job is not None
        nodes = db.scalars(select(Node).where(Node.job_id == job.id)).all()
        assert {n.kind for n in nodes} == {"segment", "audio", "subtitle", "compose", "qa"}
