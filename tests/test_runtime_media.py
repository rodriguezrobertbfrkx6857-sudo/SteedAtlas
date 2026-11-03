import io
import time
from concurrent.futures import ThreadPoolExecutor

from app.v2 import media, runtime
from app.v2.models import Node
from conftest import approved_job
from PIL import Image
from sqlalchemy import select


def test_concurrent_leases_and_fencing(system):
    c, f, h = system
    p, j = approved_job(c, h)

    def acquire(w):
        with f() as db:
            return runtime.lease(db, w)

    with ThreadPoolExecutor(2) as ex:
        results = list(ex.map(acquire, ["one", "two"]))
    assert all(results) and results[0][0] != results[1][0]
    identity, old_fence = results[0]
    with f() as db:
        n = db.get(Node, identity)
        n.lease_until = time.time() - 1
        db.commit()
    with f() as db:
        got = runtime.lease(db, "replacement")
        assert got[0] == identity and got[1] > old_fence
    with f() as db:
        assert runtime.finish(db, identity, old_fence, {}) is False


def test_cancel_idempotency_and_isolation(system):
    c, f, h = system
    p, j = approved_job(c, h)
    again = c.post(
        "/api/v2/projects/" + p["id"] + "/renders",
        headers=h["alice"],
        json={"expected_version": 2, "idempotency_key": "render-one"},
    )
    assert again.json()["id"] == j["id"]
    assert c.get("/api/v2/jobs/" + j["id"], headers=h["bob"]).status_code == 404
    c.post("/api/v2/jobs/" + j["id"] + "/cancel", headers=h["alice"])
    assert runtime.work_once() is False
    assert c.post("/api/v2/jobs/" + j["id"] + "/retry", headers=h["alice"]).status_code == 409


def test_real_cpu_video_download_and_missing_artifact(system):
    c, f, h = system
    p, j = approved_job(c, h)
    for _ in range(10):
        if not runtime.work_once():
            break
    state = c.get("/api/v2/jobs/" + j["id"], headers=h["alice"]).json()
    assert state["status"] == "SUCCEEDED", state
    final = next(n for n in state["nodes"] if n["kind"] == "qa")
    download = c.get(final["download"], headers=h["alice"])
    assert download.status_code == 200 and len(download.content) > 1000
    assert c.get(final["download"], headers=h["bob"]).status_code == 404
    subtitles = next(n for n in state["nodes"] if n["kind"] == "subtitle")
    assert "场景" in c.get(subtitles["download"], headers=h["alice"]).text
    with f() as db:
        node = db.get(Node, final["id"])
        path = media.safe_path(node.output["storage_key"])
        assert media.verify(path, 3)["decoded"]
        # Fault injection only alters this test's artifact, preserving the file for inspection.
        path.rename(path.with_suffix(".fault-missing"))
    assert c.get("/api/v2/jobs/" + j["id"], headers=h["alice"]).json()["status"] == "STALE"
    assert c.get(final["download"], headers=h["alice"]).status_code == 409


def test_real_upload_probe(system):
    c, f, h = system
    p, j = approved_job(c, h)
    image = Image.new("RGB", (320, 240), "red")
    b = io.BytesIO()
    image.save(b, format="PNG")
    r = c.post(
        "/api/v2/projects/" + p["id"] + "/assets",
        headers=h["alice"],
        files={"file": ("../../horse.exe", b.getvalue(), "application/octet-stream")},
        data={"rights": "OWNED"},
    )
    assert r.status_code == 201 and r.json()["data"]["media_type"] == "image"


def test_actual_incremental_render_reuses_unaffected_scenes(system):
    c, f, h = system
    p, j = approved_job(c, h)
    while runtime.work_once():
        pass
    with f() as db:
        original = {n.key: n.output for n in db.scalars(select(Node).where(Node.job_id == j["id"]))}
    fresh = c.get("/api/v2/projects/" + p["id"], headers=h["alice"]).json()
    data = fresh["data"]
    data["scenes"][1]["text"] = "仅第二幕字幕改变"
    saved = c.patch(
        "/api/v2/projects/" + p["id"] + "/revisions", headers=h["alice"], json={"expected_version": 2, "project": data}
    ).json()
    approved = c.post(
        "/api/v2/projects/" + p["id"] + "/approve",
        headers=h["alice"],
        json={"expected_version": saved["version"], "idempotency_key": "second-approval"},
    ).json()
    second = c.post(
        "/api/v2/projects/" + p["id"] + "/renders",
        headers=h["alice"],
        json={"expected_version": approved["version"], "idempotency_key": "render-second"},
    ).json()
    while runtime.work_once():
        pass
    state = c.get("/api/v2/jobs/" + second["id"], headers=h["alice"]).json()
    assert state["status"] == "SUCCEEDED", state
    with f() as db:
        outputs = {n.key: n.output for n in db.scalars(select(Node).where(Node.job_id == second["id"]))}
    assert outputs["scene:s1"]["storage_key"] == original["scene:s1"]["storage_key"]
    assert outputs["scene:s3"]["storage_key"] == original["scene:s3"]["storage_key"]
    assert outputs["scene:s2"]["storage_key"] != original["scene:s2"]["storage_key"]
    assert outputs["compose"]["sha256"] != original["compose"]["sha256"]


def test_vertical_chinese_output(system):
    from conftest import project_data

    c, f, h = system
    data = project_data()
    data.update(width=720, height=1280)
    p = c.post("/api/v2/projects", headers=h["alice"], json=data).json()
    p = c.post(
        "/api/v2/projects/" + p["id"] + "/approve",
        headers=h["alice"],
        json={"expected_version": 1, "idempotency_key": "vertical-approval"},
    ).json()
    j = c.post(
        "/api/v2/projects/" + p["id"] + "/renders",
        headers=h["alice"],
        json={"expected_version": p["version"], "idempotency_key": "vertical-render"},
    ).json()
    while runtime.work_once():
        pass
    state = c.get("/api/v2/jobs/" + j["id"], headers=h["alice"]).json()
    assert state["status"] == "SUCCEEDED", state
    with f() as db:
        n = db.scalar(select(Node).where(Node.job_id == j["id"], Node.kind == "qa"))
        assert (n.output["width"], n.output["height"]) == (720, 1280)
