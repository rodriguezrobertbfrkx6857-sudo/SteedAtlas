"""Read-only preflight; explicit bounded refresh delegates to the licensed pipeline."""

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

from paths import ROOT, SERVER


def owned(value):
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError("Path must stay inside project")
    return path


def inspect(database, manifest, cache):
    from app.v2.domain import digest
    from app.v2.knowledge import KnowledgeRepository
    from app.v2.source_acquisition import AcquisitionError, WikisourceProvider
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    engine = create_engine("sqlite:///file:" + database.as_posix() + "?mode=ro&uri=true")
    report = {
        "database": str(database.relative_to(ROOT)),
        "read_only": True,
        "database_sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        "python": sys.version,
        "tools": {},
        "ports": {},
        "sources": [],
        "cache": [],
        "cost_paths": "DISABLED_BY_RC_LAUNCHER; PREFLIGHT_CALLS_NO_MODEL",
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
    }
    for tool in ("node", "ffmpeg", "ffprobe"):
        executable = shutil.which(tool)
        report["tools"][tool] = (
            subprocess.run(
                [executable, "--version" if tool == "node" else "-version"], capture_output=True, text=True
            ).stdout.splitlines()[0]
            if executable
            else "MISSING"
        )
    font = os.environ.get("STEEDATLAS_FONT") or str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc")
    report["chinese_font_available"] = Path(font).is_file()
    for port in (8006, 5178):
        with socket.socket() as sock:
            report["ports"][str(port)] = "IN_USE" if sock.connect_ex(("127.0.0.1", port)) == 0 else "FREE"
    with Session(engine) as db:
        repo = KnowledgeRepository(db)
        report["coverage"] = repo.coverage()
        snapshot = KnowledgeRepository(db, snapshot_only=True)
        quotes = [c for e in snapshot.rows.values() if e.kind == "claim" and (c := snapshot.citation(e))]
        report["snapshot_quote_count"] = len(quotes)
        report["snapshot_links"] = ["/api/v2/snapshot-evidence/" + c["claim_id"] for c in quotes]
        for s in repo.rows.values():
            if s.kind != "source" or not s.data.get("upstream_revision"):
                continue
            health = repo.rows.get(s.id + "-health")
            report["sources"].append(
                {
                    "id": s.id,
                    "title": s.data["title"],
                    "revision": s.data["upstream_revision"],
                    "rights": s.data.get("rights_state"),
                    "visibility": s.data.get("visibility"),
                    "health": health.data if health else None,
                    "valid_current_quotes": sum(
                        bool(repo.citation(e))
                        for e in repo.rows.values()
                        if e.kind == "claim" and e.data.get("source_id") == s.id
                    ),
                }
            )
    engine.dispose()
    # A missing cache stays missing: do not even create its directory in read-only mode.
    provider = WikisourceProvider(cache, offline=True) if cache.is_dir() else None
    try:
        for item in json.loads(manifest.read_text(encoding="utf-8"))["sources"]:
            try:
                if not provider:
                    raise AcquisitionError("OFFLINE_CACHE_MISS")
                doc = provider.fetch(item["title"], revision=item["upstream_revision"])
                if digest({k: v for k, v in doc.items() if k != "checked_at"}) != item["document_hash"]:
                    raise AcquisitionError("MANIFEST_SNAPSHOT_MISMATCH")
                state = "CACHE_INTEGRITY_VERIFIED"
            except (AcquisitionError, KeyError, ValueError) as exc:
                state = str(exc)
            report["cache"].append({"title": item["title"], "revision": item["upstream_revision"], "state": state})
    finally:
        if provider:
            provider.close()
    report["network_requests"] = 0
    report["source_health_issues"] = [
        s["id"] for s in report["sources"] if not s["health"] or s["health"].get("status") != "AVAILABLE"
    ]
    report["missing_database_versions"] = [
        item["title"]
        for item in json.loads(manifest.read_text(encoding="utf-8"))["sources"]
        if not any(
            s["title"] == item["title"] and s["revision"] == item["upstream_revision"] for s in report["sources"]
        )
    ]
    report["status"] = (
        "PASS"
        if not report["source_health_issues"]
        and not report["missing_database_versions"]
        and report["coverage"]["machine_verified_count"]
        and report["chinese_font_available"]
        and all(v != "MISSING" for v in report["tools"].values())
        and all(x["state"] == "CACHE_INTEGRITY_VERIFIED" for x in report["cache"])
        else "ATTENTION"
    )
    report["policy"] = (
        "Current citations require successful observation <=7 days. Snapshot browsing never renews observation and never bypasses hashes, rights, withdrawal or private access. Missing cache: run resume_demo.py replay online."
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--manifest", default="reports/rag-upgrade/autonomous/source-manifest.json")
    parser.add_argument("--cache", default="runtime/source-cache")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--refresh-pages", type=int, default=0)
    parser.add_argument("--report", default="reports/resume-readiness/preflight.json")
    args = parser.parse_args()
    database, manifest, cache, output = map(owned, (args.database, args.manifest, args.cache, args.report))
    if not database.is_file() or database == ROOT / "runtime/steedatlas.db":
        raise SystemExit("Existing isolated database required; original runtime/steedatlas.db refused")
    if args.refresh_pages:
        if args.offline or not 1 <= args.refresh_pages <= 6:
            raise SystemExit("Refresh requires online mode and 1..6 pages")
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/resume_demo.py"),
                "replay",
                "--database",
                str(database),
                "--manifest",
                str(manifest),
                "--cache",
                str(cache),
                "--refresh",
                "--max-pages",
                str(args.refresh_pages),
            ],
            check=True,
        )
    os.environ.update(
        DATABASE_URL="sqlite:///" + database.as_posix(),
        SECRET_KEY="preflight-readonly-" + "x" * 48,
        DEBUG="false",
        STEEDATLAS_ROOT=str(ROOT),
    )
    sys.path.insert(0, str(SERVER))
    report = inspect(database, manifest, cache)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {k: report[k] for k in ("status", "coverage", "snapshot_quote_count", "network_requests")},
            ensure_ascii=False,
        )
    )
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
