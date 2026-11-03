"""Actual licensed-source boundary demonstration on a new disposable DB copy."""

import json
import os
import sqlite3
import sys
import time

from paths import ROOT, SERVER

source = ROOT / "runtime/resume-rc/autonomous-demo.db"
target = ROOT / f"runtime/autonomous-failure-demo-{time.time_ns()}.db"
with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src, sqlite3.connect(target) as dst:
    src.backup(dst)
os.environ.update(
    DATABASE_URL="sqlite:///" + target.as_posix(),
    SECRET_KEY="local-failure-demo-" + "x" * 48,
    DEBUG="false",
    STEEDATLAS_ROOT=str(ROOT),
)
sys.path.insert(0, str(SERVER))
from app.database import SessionLocal
from app.v2.domain import revise
from app.v2.knowledge import AnswerService, KnowledgeRepository
from app.v2.source_acquisition import ingest_document

report = {"scope": "ISOLATED_COPY_REAL_LICENSED_DOCUMENTS", "database": str(target.relative_to(ROOT))}
with SessionLocal() as db:
    repo = KnowledgeRepository(db)
    date = AnswerService(db).answer([{"role": "user", "content": "赤兔出生于哪年哪月哪日？"}])
    assert date["mode"] == "INSUFFICIENT"
    report["unsupported_date"] = date
    literary = AnswerService(db).answer([{"role": "user", "content": "的卢在三国演义里的故事原文"}], "literature")
    assert literary["mode"] == "LITERARY_ATTRIBUTED"
    assert all(c["genre"] == "LITERARY_WORK" for c in literary["citations"])
    report["literature_not_fact"] = literary
    citation = next(
        c
        for e in repo.rows.values()
        if e.kind == "claim" and (c := repo.citation(e)) and c["source_title"] == "三國志/卷07"
    )
    source_row = repo.rows[citation["source_id"]]
    doc = {k: v for k, v in repo.rows[source_row.data["document_id"]].data.items() if k != "visibility"}
    doc["checked_at"] = repo.rows[source_row.id + "-health"].data["checked_at"]
    catalogue = [
        {"id": r["id"], "name": r["name"], "aliases": repo.rows[r["id"]].data.get("aliases", [])}
        for r in repo.editorial
    ]
    before = repo.coverage()["machine_verified_count"]
    duplicate = ingest_document(db, doc, catalogue, True)
    db.commit()
    after = KnowledgeRepository(db).coverage()["machine_verified_count"]
    assert before == after and duplicate["new_claims"] == 0
    report["duplicate"] = {"before": before, "after": after, "result": duplicate}
    revise(db, source_row, source_row.version, {**source_row.data, "review_state": "RETIRED"}, "local-demo")
    db.commit()
    assert not KnowledgeRepository(db).validate(citation)
    assert not KnowledgeRepository(db, snapshot_only=True).citation(repo.rows[citation["claim_id"]])
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        page = client.get(citation["href"])
        snapshot = client.get("/api/v2/snapshot-evidence/" + citation["claim_id"])
    assert "STALE" in page.text and snapshot.status_code == 404
    report["withdrawal"] = {
        "old_citation_valid": False,
        "old_page_marked_stale": True,
        "snapshot_http": snapshot.status_code,
    }
(ROOT / "reports/resume-readiness/failure-demonstrations.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(
    "PASS: unsupported date, literature attribution, duplicate import and source withdrawal; original RC DB untouched"
)
