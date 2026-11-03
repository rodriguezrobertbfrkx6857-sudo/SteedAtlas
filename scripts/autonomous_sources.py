"""Acquire bounded Wikisource evidence into an explicitly isolated database.

First: --new-copy --apply --seed-only. Then reuse runtime/autonomous-demo-path.txt.
Default is a true DB dry run. Raw source caches and database are never committed.
"""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from collections import Counter
from urllib.parse import quote

from paths import ROOT, SERVER


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new-copy", action="store_true")
    parser.add_argument("--database")
    parser.add_argument("--copy-from", help="Existing project database used read-only with --new-copy")
    parser.add_argument(
        "--manifest", help="Project-owned JSON source manifest; replay pinned revisions without discovery"
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--entities", default="chitu,wuzhui,dilu")
    parser.add_argument("--seed-only", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--max-requests", type=int, default=30)
    parser.add_argument("--max-pages", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.max_requests <= 300 or not 1 <= args.max_pages <= 100:
        raise SystemExit("Bounded batch required: requests 1..300, pages 1..100")
    output = ROOT / "reports/rag-upgrade/autonomous"
    output.mkdir(parents=True, exist_ok=True)
    pointer = ROOT / "runtime/autonomous-demo-path.txt"
    if args.new_copy:
        previous = ROOT / "runtime/rag-demo-path.txt"
        source = (
            ROOT / (args.copy_from or (previous.read_text().strip() if previous.exists() else "runtime/steedatlas.db"))
        ).resolve()
        if not source.is_relative_to(ROOT) or not source.exists():
            raise SystemExit("Project-owned baseline copy required")
        path = ROOT / f"runtime/autonomous-{time.time_ns()}.db"
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src, sqlite3.connect(path) as dst:
            src.backup(dst)
        pointer.write_text(str(path.relative_to(ROOT)), encoding="utf-8")
        protected = ROOT / "runtime/steedatlas.db"
        manifest = {
            "database": str(path.relative_to(ROOT)),
            "copy_of": str(source.relative_to(ROOT)),
            "protected_db_sha256": hashlib.sha256(protected.read_bytes()).hexdigest(),
            "original_assets_sha256": {
                str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((ROOT / "wangzhan/baiqipu.com-source-20260424-194149/assets").rglob("*"))
                if p.is_file()
            },
            "original_dirty_report_sha256": hashlib.sha256(
                (ROOT / "reports/original-video-factory-v2.json").read_bytes()
            ).hexdigest(),
        }
        (ROOT / "runtime/autonomous-protection.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
    else:
        path = (ROOT / (args.database or pointer.read_text().strip())).resolve()
    if not path.is_relative_to(ROOT / "runtime") or not path.name.startswith("autonomous-") or not path.exists():
        raise SystemExit("Only existing runtime/autonomous-*.db isolated copies are accepted")
    os.environ.update(
        DATABASE_URL="sqlite:///" + path.as_posix(),
        DEBUG="false",
        SECRET_KEY="offline-source-pipeline-" + "x" * 48,
        STEEDATLAS_ROOT=str(ROOT),
    )
    sys.path.insert(0, str(SERVER))
    from app.database import SessionLocal
    from app.v2.domain import digest, revise
    from app.v2.knowledge import KnowledgeRepository
    from app.v2.knowledge_api import invalidate_dependents
    from app.v2.models import Entity
    from app.v2.source_acquisition import SEEDS, AcquisitionError, WikisourceProvider, ingest_document

    provider = WikisourceProvider(ROOT / "runtime/source-cache", args.max_requests, offline=args.offline)
    report = {
        "database": str(path.relative_to(ROOT)),
        "mode": "APPLY" if args.apply else "DRY_RUN",
        "discoveries": [],
        "imports": [],
        "quarantined": [],
        "human_reviewed": 0,
    }
    attempted = set()
    with SessionLocal() as db:
        repo = KnowledgeRepository(db)
        report["before_snapshot"] = repo.snapshot
        catalogue = [
            {
                "id": r["id"],
                "name": r["name"],
                "aliases": repo.rows[r["id"]].data.get("aliases", []) if r["id"] in repo.rows else [],
            }
            for r in repo.editorial
        ]
        chosen = catalogue if args.entities == "all" else [e for e in catalogue if e["id"] in args.entities.split(",")]

        def acquire(title, revision=None, expected_hash=None):
            if title in attempted or len(attempted) >= args.max_pages:
                return
            attempted.add(title)
            try:
                doc = provider.fetch(title, refresh=args.refresh, revision=revision)
                if expected_hash and digest({k: v for k, v in doc.items() if k != "checked_at"}) != expected_hash:
                    raise AcquisitionError("MANIFEST_SNAPSHOT_MISMATCH")
                with db.begin_nested():
                    result = ingest_document(db, doc, catalogue, args.apply)
                if args.apply:
                    db.commit()
                report["imports"].append(result)
                print(json.dumps(result, ensure_ascii=False), flush=True)
            except (AcquisitionError, KeyError, TypeError) as exc:
                reason = str(exc)
                report["quarantined"].append({"title": title, "reason": reason})
                # A failed online refresh invalidates dependents. Budget/cache miss is
                # not evidence of source disappearance; the 7-day validity lease remains.
                if args.apply and reason not in (
                    "REQUEST_BUDGET",
                    "OFFLINE_CACHE_MISS",
                    "MANIFEST_SNAPSHOT_MISMATCH",
                    "WRONG_EDITION",
                ):
                    for source in KnowledgeRepository(db).rows.values():
                        if (
                            source.kind == "source"
                            and source.data.get("title") == title
                            and source.data.get("provider") == "wikisource"
                        ):
                            health = db.get(Entity, source.id + "-health")
                            if health:
                                revise(
                                    db,
                                    health,
                                    health.version,
                                    {**health.data, "status": "UNAVAILABLE", "reason": reason[:200]},
                                    "source-pipeline",
                                )
                            invalidate_dependents(db, source.id, "source-pipeline")
                    db.commit()
                print(json.dumps({"quarantined": title, "reason": reason}, ensure_ascii=False), flush=True)

        if args.manifest:
            manifest_path = (ROOT / args.manifest).resolve()
            if not manifest_path.is_relative_to(ROOT):
                raise SystemExit("Project-owned manifest required")
            for source in json.loads(manifest_path.read_text(encoding="utf-8"))["sources"][: args.max_pages]:
                acquire(source["title"], source["upstream_revision"], source.get("document_hash"))
        else:
            for e in chosen:
                for title in SEEDS.get(e["id"], []):
                    acquire(title)
        if not args.seed_only and not args.manifest:
            for e in chosen:
                try:
                    candidates = provider.discover(e)
                    report["discoveries"].append({"entity": e, "candidates": candidates})
                    print(
                        json.dumps({"discovered": e["name"], "candidates": candidates}, ensure_ascii=False), flush=True
                    )
                    for c in candidates:
                        if c["permitted_work"]:
                            acquire(c["title"])
                        else:
                            report["quarantined"].append({"title": c["title"], "reason": "WORK_EDITION_RIGHTS_UNKNOWN"})
                except AcquisitionError as exc:
                    report["discoveries"].append({"entity": e, "reason": str(exc)})
        repo = KnowledgeRepository(db)
        verified = [repo.citation(c) for c in repo.rows.values() if c.kind == "claim"]
        verified = [c for c in verified if c]
        rows = []
        for e in catalogue:
            citations = [c for c in verified if e["id"] in repo.subjects(repo.rows[c["claim_id"]])]
            discovery = next((d for d in report["discoveries"] if d["entity"]["id"] == e["id"]), None)
            candidates = discovery.get("candidates", []) if discovery else []
            state = (
                "AUTO_VERIFIED_SOURCE"
                if citations
                else "NOT_DISCOVERED_IN_THIS_BATCH"
                if discovery is None
                else "DISCOVERY_FAILED"
                if discovery.get("reason")
                else "NO_SOURCE_FOUND"
                if not candidates
                else "AMBIGUOUS_OR_NO_EXACT_PASSAGE"
                if any(c["permitted_work"] for c in candidates)
                else "WORK_RIGHTS_POLICY_QUARANTINED"
            )
            rows.append(
                {
                    **e,
                    "verified_quote_count": len(citations),
                    "source_ids": sorted({c["source_id"] for c in citations}),
                    "genres": sorted({c["genre"] for c in citations}),
                    "state": state,
                    "source_only_links": [
                        {
                            "title": c["title"],
                            "url": "https://zh.wikisource.org/wiki/" + quote(c["title"]),
                            "rights_checked": c["permitted_work"],
                        }
                        for c in candidates
                    ],
                    "quarantined_candidates": sum(not c["permitted_work"] for c in candidates),
                    "entity_identity": "ALIAS_CANDIDATE_NOT_HISTORICAL_IDENTITY_PROOF",
                }
            )
        coverage = {
            **repo.coverage(),
            "entities_with_verified_quotes": sum(bool(e["verified_quote_count"]) for e in rows),
            "catalogue_size": len(rows),
            "sources": len({c["source_id"] for c in verified}),
            "source_records_stored": sum(e.kind == "source" for e in repo.rows.values()),
            "licensed_acquired_sources": sum(
                e.kind == "source" and e.data.get("provider") == "wikisource" for e in repo.rows.values()
            ),
            "state_counts": dict(Counter(e["state"] for e in rows)),
            "entity_types": dict(
                Counter(
                    e.data.get("entity_type", "UNKNOWN") for e in repo.rows.values() if e.kind == "knowledge_entity"
                )
            ),
            "entities": rows,
            "historical_accuracy": "UNVERIFIED_NO_HUMAN_GOLD",
            "provenance_levels": {"EXACT_REVISION_MATCH": len(verified)},
        }
        if args.apply:
            (output / "corpus_coverage.json").write_text(
                json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        report["coverage"] = {k: v for k, v in coverage.items() if k != "entities"}
        report["after_snapshot"] = repo.snapshot
        report["knowledge_unchanged"] = report["before_snapshot"] == report["after_snapshot"]
    provider.close()
    report["requests"] = provider.calls
    report["trace"] = provider.trace
    filename = f"acquisition-{'apply' if args.apply else 'dry-run'}-{time.time_ns()}.json"
    (output / filename).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps({"report": filename, "coverage": report["coverage"], "requests": provider.calls}, ensure_ascii=False)
    )


if __name__ == "__main__":
    main()
