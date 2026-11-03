"""Unmocked source/answer/agent comparison with explicitly non-gold proxy metrics."""

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time

from paths import ROOT, SERVER

sys.stdout.reconfigure(encoding="utf-8")
parser = argparse.ArgumentParser()
parser.add_argument("--database")
parser.add_argument("--output", default="reports/rag-upgrade/autonomous")
args = parser.parse_args()
from resume_demo_preflight import owned

database = owned(args.database or (ROOT / "runtime/autonomous-demo-path.txt").read_text().strip())
os.environ.update(
    DATABASE_URL="sqlite:///" + database.as_posix(),
    DEBUG="false",
    STEEDATLAS_ROOT=str(ROOT),
    SECRET_KEY="offline-acceptance-" + "x" * 48,
    SOURCE_AUTODISCOVERY_ENABLED="1",
)
sys.path.insert(0, str(SERVER))
from app.database import SessionLocal
from app.v2.domain import rank
from app.v2.knowledge import AnswerService, EvidenceSearch, KnowledgeRepository, normalize
from app.v2.research import ResearchAgent, ResearchPolicy
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

out = owned(args.output)
out.mkdir(parents=True, exist_ok=True)
with SessionLocal() as db:
    repo = KnowledgeRepository(db)
    queries = [
        ("赤兔的史籍出处是什么？", "history"),
        ("乌骓的原文", "history"),
        ("的卢的史料有哪些？", "history"),
        ("赤兔在三国演义里如何描写？", "literature"),
        ("赤兔和的卢的来源比较", "history"),
        ("赤菟有哪些记载？", "all"),
        ("苍麟驹的史料出处", "history"),
        ("我重视责任和守护，哪匹马适合我？", "all"),
        ("推荐赤兔周边商品，预算600元", "all"),
        ("赤兔出生于哪年哪月哪日？", "history"),
    ]
    samples = []
    for query, scope in queries:
        started = time.monotonic()
        answer = AnswerService(db).answer([{"role": "user", "content": query}], scope)
        samples.append(
            {
                "query": query,
                "scope": scope,
                "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
                "answer": answer,
            }
        )
        assert all(repo.validate(c) for c in answer["citations"])
    followup = AnswerService(db).answer(
        [
            {"role": "user", "content": "乌骓"},
            {"role": "assistant", "content": "引文见上"},
            {"role": "user", "content": "它的史书原文呢？"},
        ]
    )
    assert followup["citations"]
    assert samples[6]["answer"]["mode"] == "INSUFFICIENT"
    assert samples[7]["answer"]["matched_horse"] and samples[7]["answer"]["recommended_product"] is None
    assert samples[8]["answer"]["recommended_product"]
    assert samples[9]["answer"]["mode"] == "INSUFFICIENT"
    valid = [repo.citation(c) for c in repo.rows.values() if c.kind == "claim"]
    valid = [c for c in valid if c]
    subjects = sorted({s for c in valid for s in repo.subjects(repo.rows[c["claim_id"]])})
    old_coverage = json.loads(
        (ROOT / "reports/rag-upgrade/autonomous/corpus_coverage.json").read_text(encoding="utf-8")
    )
    coverage = {
        **repo.coverage(),
        "entities_with_verified_quotes": len(subjects),
        "entities": subjects,
        "source_versions_with_quotes": len({(c["source_id"], c["source_revision"]) for c in valid}),
        "independent_works_with_mentions": len({repo.rows[c["source_id"]].data.get("work") for c in valid}),
        "licensed_versions_stored": sum(
            e.kind == "source" and e.data.get("provider") == "wikisource" for e in repo.rows.values()
        ),
        "meaning": "MENTIONS quotation relations, not historical facts or independent support",
        "previous_snapshot": {
            k: old_coverage[k] for k in ("machine_verified_count", "entities_with_verified_quotes", "sources")
        },
    }
    (out / "coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")
    documents = [
        {"id": c["claim_id"], "text": normalize(c["quote"] + repo.rows[c["claim_id"]].data["text"])} for c in valid
    ]
    benchmark = []
    for identity in subjects:
        name = next(r["name"] for r in repo.editorial if r["id"] == identity)
        query = name + "的原文出处"
        expected = {c["claim_id"] for c in valid if identity in repo.subjects(repo.rows[c["claim_id"]])}
        row = {"entity": identity, "query": query, "expected_from": "MACHINE_ALIAS_LINKS_NOT_HUMAN_GOLD"}
        for algorithm in ("cosine", "bm25"):
            start = time.monotonic()
            hits = rank(normalize(query), documents, algorithm)[:5]
            row[algorithm] = {
                "ids": [h["id"] for h in hits],
                "any_linked_at_5": bool(expected & {h["id"] for h in hits}),
                "elapsed_ms": round((time.monotonic() - start) * 1000, 3),
            }
        scoped = EvidenceSearch(repo).search(query, "all", 5)["results"]
        row["unified_scoped"] = {
            "ids": [h["id"] for h in scoped],
            "any_linked_at_5": bool(expected & {h["id"] for h in scoped}),
        }
        benchmark.append(row)
    strategies = []
    for query in ("赤兔的来源", "赤兔和的卢的史料比较", "苍麟驹的史料出处"):
        for strategy in ("single", "fixed", "adaptive"):
            result = ResearchAgent(db).run(query, strategy)
            strategies.append(
                {
                    "query": query,
                    "strategy": strategy,
                    "calls": len(result["trace"]),
                    "evidence": len(result["evidence"]),
                    "stop_reason": result["stop_reason"],
                    "trace": result["trace"],
                }
            )
    report = {
        "corpus_snapshot_id": repo.snapshot,
        "coverage": repo.coverage(),
        "scope": "SOURCE_INTEGRITY_AND_ALIAS_PROXY_NOT_HISTORICAL_ACCURACY",
        "samples": samples,
        "multi_turn": followup,
        "candidate_benchmark": benchmark,
        "retrieval_summary": {
            a: {"any_linked_at_5": sum(r[a]["any_linked_at_5"] for r in benchmark), "queries": len(benchmark)}
            for a in ("cosine", "bm25", "unified_scoped")
        },
        "old_approved_gate": {
            "usable_claims": sum(
                c.data.get("review_state") == "APPROVED" and bool(repo.citation(c))
                for c in repo.rows.values()
                if c.kind == "claim"
            )
        },
        "new_machine_track": {"usable_claims": len(valid), "human_reviewed": 0},
        "answer_latency_ms": {
            "median": statistics.median(r["elapsed_ms"] for r in samples),
            "max": max(r["elapsed_ms"] for r in samples),
        },
        "agent_strategies": strategies,
        "unverified": [
            "historical accuracy",
            "claim entailment",
            "expert citation precision",
            "dense/hybrid benefit",
            "Jev/live LLM benefit",
        ],
        "paid_api_calls": 0,
    }
    (out / "rag-comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

# A second isolated baseline copy demonstrates actual acquisition through the
# Agent's tools. Provider is real; cache/FETCHED flags report exactly what happened.
agent_db = ROOT / f"runtime/autonomous-agent-rc-{time.time_ns()}.db"
subprocess.run(
    [sys.executable, str(ROOT / "scripts/resume_demo.py"), "init", "--database", str(agent_db)],
    check=True,
    stdout=subprocess.DEVNULL,
)
engine = create_engine("sqlite:///" + agent_db.as_posix())
with Session(engine) as db:
    before = KnowledgeRepository(db).coverage()
    run = ResearchAgent(
        db, ResearchPolicy(max_calls=10, max_seconds=45, allow_acquisition=True), owner="acceptance"
    ).run("赤兔的史籍出处", "single")
    after = KnowledgeRepository(db).coverage()
    (out / "agent-acquisition-trace.json").write_text(
        json.dumps(
            {
                "database": str(agent_db.relative_to(ROOT)),
                "provider_mocked": False,
                "before": before,
                "run": run,
                "after": after,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    assert before["machine_verified_count"] == 0 and after["machine_verified_count"] > 0
    assert "acquire_source" in [r["tool"] for r in run["trace"]]
engine.dispose()
protected = json.loads((ROOT / "runtime/autonomous-protection.json").read_text(encoding="utf-8"))
checks = {
    "original_database_unchanged": hashlib.sha256((ROOT / "runtime/steedatlas.db").read_bytes()).hexdigest()
    == protected["protected_db_sha256"],
    "original_assets_unchanged": all(
        hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in protected["original_assets_sha256"].items()
    ),
    "preexisting_dirty_report_unchanged": hashlib.sha256(
        (ROOT / "reports/original-video-factory-v2.json").read_bytes()
    ).hexdigest()
    == protected["original_dirty_report_sha256"],
    "checked_asset_files": len(protected["original_assets_sha256"]),
}
(out / "data-protection.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
assert all(checks.values())
print(
    json.dumps(
        {
            "retrieval": report["retrieval_summary"],
            "coverage": report["coverage"],
            "protection": checks,
            "agent_acquisition": after["machine_verified_count"],
        },
        ensure_ascii=False,
    )
)
