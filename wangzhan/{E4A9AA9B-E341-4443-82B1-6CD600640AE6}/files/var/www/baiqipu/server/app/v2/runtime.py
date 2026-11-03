import os
import threading
import time

from sqlalchemy import or_, select, update

from app.database import SessionLocal

from . import media
from .domain import canonical_timeline, digest, emit
from .models import Entity, Job, Node

KINDS = {"segment", "subtitle", "audio", "compose", "qa"}
TOOL_VERSION = "ffmpeg-timeline-2-unicode-font"


def validate_dag(nodes):
    if not 1 <= len(nodes) <= 64:
        raise ValueError("NODE_LIMIT")
    lookup = {n["key"]: n for n in nodes}
    if len(lookup) != len(nodes):
        raise ValueError("DUPLICATE_NODE")
    for n in nodes:
        if n["kind"] not in KINDS or any(d not in lookup for d in n["deps"]):
            raise ValueError("INVALID_NODE_OR_DEPENDENCY")
    done = set()
    while len(done) < len(nodes):
        ready = {k for k, n in lookup.items() if k not in done and set(n["deps"]) <= done}
        if not ready:
            raise ValueError("CYCLE_DETECTED")
        done |= ready
    return True


def claim_guard(db, project):
    from .knowledge import KnowledgeRepository

    repo = KnowledgeRepository(db)
    for s in project["scenes"]:
        for ref in s["claim_refs"]:
            try:
                identity, version = ref.rsplit("@", 1)
                c = db.get(Entity, identity)
                if not c or c.kind != "claim" or c.version != int(version):
                    raise ValueError()
                citation = repo.citation(c)
                if not citation:
                    raise ValueError()
                if citation["verification"] == "MACHINE_VERIFIED":
                    expected = "LITERARY_ATTRIBUTED" if citation["genre"] == "LITERARY_WORK" else "SOURCE_ATTRIBUTED"
                    if s["label"] != expected or len(s["text"]) < 8 or s["text"] not in citation["quote"]:
                        raise ValueError()
                elif c.data.get("review_state") != "APPROVED" or c.data["epistemic_status"] != s["label"]:
                    raise ValueError()
            except (ValueError, KeyError):
                raise ValueError("CLAIM_REVIEW_REQUIRED") from None
        if s["label"] != "CREATIVE" and not s["claim_refs"]:
            raise ValueError("MISSING_CITATION")


def compile_plan(db, entity):
    p = entity.data
    claim_guard(db, p)
    nodes = []
    for i, s in enumerate(p["scenes"]):
        asset = None
        if s["asset_id"]:
            e = db.get(Entity, s["asset_id"])
            if not e or e.kind != "asset" or e.owner != entity.owner:
                raise ValueError("ASSET_NOT_OWNED")
            if e.data["media_type"] not in {"image", "video"} or not media.valid_artifact(e.data):
                raise ValueError("INVALID_VISUAL_ASSET")
            asset = e.data
        minimal = {k: p[k] for k in ["width", "height", "fps_num", "bible"]}
        from .knowledge import KnowledgeRepository

        repo = KnowledgeRepository(db)
        citations = [repo.citation(repo.rows[ref.rsplit("@", 1)[0]]) for ref in s["claim_refs"]]
        params = {"scene": s, "project": minimal, "asset": asset, "index": i, "citations": citations}
        nodes.append({"key": "scene:" + s["id"], "kind": "segment", "deps": [], "params": params})
    audio = []
    for identity in p["audio_asset_ids"]:
        e = db.get(Entity, identity)
        if (
            not e
            or e.owner != entity.owner
            or e.kind != "asset"
            or e.data["media_type"] != "audio"
            or not media.valid_artifact(e.data)
        ):
            raise ValueError("INVALID_AUDIO_ASSET")
        audio.append(e.data)
    nodes += [
        {"key": "audio", "kind": "audio", "deps": [], "params": {"assets": audio}},
        {"key": "subtitle", "kind": "subtitle", "deps": ["audio"], "params": {"project": p}},
        {
            "key": "compose",
            "kind": "compose",
            "deps": ["scene:" + s["id"] for s in p["scenes"]] + ["audio", "subtitle"],
            "params": {"project": p, "audio": audio},
        },
        {"key": "qa", "kind": "qa", "deps": ["compose"], "params": {"timeline": canonical_timeline(p)}},
    ]
    fingerprints = {}
    for n in nodes:
        n["fingerprint"] = digest(
            {
                "kind": n["kind"],
                "params": n["params"],
                "tool": TOOL_VERSION,
                "deps": [fingerprints[d] for d in n["deps"]],
            }
        )
        fingerprints[n["key"]] = n["fingerprint"]
    validate_dag(nodes)
    return nodes


def lease(db, worker, now=None):
    now = now or time.time()
    jobs = db.scalars(select(Job).where(Job.status.in_(["READY", "RUNNING"]))).all()
    for job in jobs:
        nodes = db.scalars(select(Node).where(Node.job_id == job.id)).all()
        states = {n.key: n.state for n in nodes}
        for n in nodes:
            if n.state == "RUNNING" and n.lease_until < now and n.attempts >= 3:
                n.state = "FAILED_FINAL"
                n.error = "RECOVERY_BUDGET_EXHAUSTED"
                job.status = "FAILED_FINAL"
                emit(db, job.id, worker, "RECOVERY_BUDGET_EXHAUSTED", {"node": n.key})
                db.commit()
                continue
            if n.attempts >= 3 or not all(states.get(d) == "SUCCEEDED" for d in n.deps):
                continue
            available = or_(Node.state == "READY", (Node.state == "RUNNING") & (Node.lease_until < now))
            changed = db.execute(
                update(Node)
                .where(Node.id == n.id, Node.fence == n.fence, available)
                .values(
                    state="RUNNING", fence=n.fence + 1, attempts=n.attempts + 1, worker=worker, lease_until=now + 240
                )
            )
            if changed.rowcount:
                job.status = "RUNNING"
                emit(db, job.id, worker, "LEASED", {"node": n.key, "fence": n.fence})
                db.commit()
                db.refresh(n)
                return n.id, n.fence
    return None


def finish(db, node_id, fence, output):
    db.expire_all()
    n = db.get(Node, node_id)
    job = db.get(Job, n.job_id)
    if job.status == "CANCELLED" or n.fence != fence or n.lease_until < time.time() or n.state != "RUNNING":
        return False
    claim_guard(db, job.snapshot)
    if not media.valid_artifact(output):
        raise ValueError("INVALID_OUTPUT")
    changed = db.execute(
        update(Node)
        .where(Node.id == node_id, Node.fence == fence, Node.state == "RUNNING", Node.lease_until > time.time())
        .values(state="SUCCEEDED", output=output, lease_until=0)
    )
    if not changed.rowcount:
        return False
    emit(db, job.id, n.worker, "SUCCEEDED", {"node": n.key, "sha256": output["sha256"], "fence": fence})
    db.flush()
    if all(x.state == "SUCCEEDED" for x in db.scalars(select(Node).where(Node.job_id == job.id)).all()):
        job.status = "SUCCEEDED"
    db.commit()
    return True


def work_once(worker="local-worker"):
    with SessionLocal() as db:
        acquired = lease(db, worker)
        if not acquired:
            return False
        node_id, fence = acquired
        n = db.get(Node, node_id)
        job = db.get(Job, n.job_id)
        stop = threading.Event()

        def heartbeat():
            while not stop.wait(20):
                with SessionLocal() as renew:
                    changed = renew.execute(
                        update(Node)
                        .where(
                            Node.id == node_id,
                            Node.fence == fence,
                            Node.state == "RUNNING",
                            Node.lease_until > time.time(),
                        )
                        .values(lease_until=time.time() + 240)
                    )
                    renew.commit()
                    if not changed.rowcount:
                        return

        pulse = threading.Thread(target=heartbeat, daemon=True)
        pulse.start()
        try:
            claim_guard(db, job.snapshot)
            # Reuse only verified outputs in the same ACL domain. Missing bytes never count as cache hits.
            candidates = db.scalars(
                select(Node)
                .join(Job, Node.job_id == Job.id)
                .where(Job.owner == job.owner, Node.fingerprint == n.fingerprint, Node.state == "SUCCEEDED")
            ).all()
            output = next((c.output for c in candidates if media.valid_artifact(c.output)), None)
            if output:
                emit(db, job.id, worker, "CACHE_REUSED", {"node": n.key, "fingerprint": n.fingerprint})
            else:
                target = media.STORE / job.id / f"{n.id}-{fence}"
                target.parent.mkdir(parents=True, exist_ok=True)
                if n.kind == "segment":
                    output = media.segment(n.params, target.with_suffix(".mp4"))
                elif n.kind == "subtitle":
                    p = target.with_suffix(".srt")
                    p.write_text(media.srt(job.snapshot), encoding="utf-8")
                    output = media.artifact(p)
                elif n.kind == "audio":
                    for a in n.params["assets"]:
                        if not media.valid_artifact(a):
                            raise ValueError("INVALID_AUDIO")
                    p = target.with_suffix(".json")
                    p.write_text(
                        __import__("json").dumps(
                            {"mode": "UPLOADED" if n.params["assets"] else "SILENT", "alignment": "MANUAL_SCENE_TIMING"}
                        ),
                        encoding="utf-8",
                    )
                    output = media.artifact(p)
                elif n.kind == "compose":
                    deps = db.scalars(select(Node).where(Node.job_id == job.id, Node.kind == "segment")).all()
                    ordered = sorted(deps, key=lambda x: x.params["index"])
                    output = media.compose(
                        job.snapshot, [x.output for x in ordered], n.params["audio"], target.with_suffix(".mp4")
                    )
                else:
                    c = db.scalar(select(Node).where(Node.job_id == job.id, Node.key == "compose"))
                    output = {**c.output, **media.verify(media.safe_path(c.output["storage_key"]))}
            finish(db, node_id, fence, output)
        except Exception as exc:
            db.rollback()
            n = db.get(Node, node_id)
            job = db.get(Job, n.job_id)
            if n.fence == fence and job.status != "CANCELLED":
                n.state = "INVALID_OUTPUT" if isinstance(exc, ValueError) else "FAILED_FINAL"
                n.error = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
                n.error = n.error[:160]
                job.status = "NEEDS_REVIEW" if "CLAIM" in n.error else "FAILED_FINAL"
                emit(db, job.id, worker, n.state, {"node": n.key, "error_code": n.error})
                db.commit()
        finally:
            stop.set()
            pulse.join(timeout=1)
        return True


def main():
    worker = "worker-" + str(os.getpid())
    while True:
        # Database-specific liveness; no hard-coded connected=true capability.
        with SessionLocal() as db:
            pulse = db.get(Entity, "local-worker-heartbeat")
            if pulse:
                pulse.data = {"last_seen": time.time(), "worker": worker}
            else:
                db.add(
                    Entity(
                        id="local-worker-heartbeat",
                        kind="worker_heartbeat",
                        owner="system",
                        data={"last_seen": time.time(), "worker": worker},
                    )
                )
            db.commit()
        if not work_once(worker):
            time.sleep(0.5)


if __name__ == "__main__":
    main()
