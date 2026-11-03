"""Run API or worker against the same local V2 database. No external provider calls."""

import argparse
import json
import os
import secrets
import sqlite3
import sys

from paths import ROOT, SERVER

parser = argparse.ArgumentParser()
parser.add_argument("command", choices=["init", "api", "worker"])
parser.add_argument("--port", type=int, default=8002)
parser.add_argument("--database", default="runtime/steedatlas.db", help="Project-owned database; use a copy for QA")
parser.add_argument(
    "--import-local-backup",
    action="store_true",
    help="Copy the project-owned read-only baseline backup to V2 development DB",
)
args = parser.parse_args()
runtime = ROOT / "runtime"
runtime.mkdir(exist_ok=True)
database = (ROOT / args.database).resolve()
if not database.is_relative_to(ROOT.resolve()):
    raise SystemExit("Database must stay inside the authorized project")
key = runtime / "development-secret.txt"
if not key.exists():
    key.write_text(secrets.token_urlsafe(48))
os.environ.update(
    DATABASE_URL="sqlite:///" + database.as_posix(),
    SECRET_KEY=key.read_text(),
    DEBUG="false",
    STEEDATLAS_ROOT=str(ROOT),
    VIDEO_FACTORY_API_MODE="off",
    LEGACY_EXTERNAL_ENABLED="false",
    WORKFLOW_RUNTIME_REDIS_ENABLED="false",
    EXTERNAL_VIDEO_ENABLED="false",
    PUBLICATION_ENABLED="false",
    AGENT_PROVIDER_MODE="MANUAL",
    SOURCE_AUTODISCOVERY_ENABLED="1" if database.name.startswith("autonomous-") else "0",
)
sys.path.insert(0, str(SERVER))
os.chdir(SERVER)

if args.command == "init":
    if args.import_local_backup and not database.exists():
        original = ROOT / "runtime/backups/legacy.db"
        if not original.exists():
            raise SystemExit("No local baseline backup; run init without --import-local-backup for empty DB")
        source = sqlite3.connect(original.as_uri() + "?mode=ro", uri=True)
        target = sqlite3.connect(database)
        source.backup(target)
        target.close()
        source.close()
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(SERVER / "alembic.ini")), "head")
    from app.database import SessionLocal
    from app.v2.domain import create, digest
    from app.v2.models import Entity
    from sqlalchemy import select

    with SessionLocal() as db:
        if not db.scalar(select(Entity).where(Entity.kind == "source")):
            for i, row in enumerate(json.loads((SERVER / "data/v2_evidence_seed.json").read_text(encoding="utf-8")), 1):
                sid, pid, cid = f"source-{i}", f"passage-{i}", f"claim-{i}"
                create(
                    db,
                    "source",
                    "curation",
                    {
                        "title": row["title"],
                        "url": row["url"],
                        "kind": row["kind"],
                        "language": "zh-Hant",
                        "rights_status": "PUBLIC_DOMAIN_TEXT_EXCERPT; edition/site terms require review",
                        "reliability": "UNREVIEWED",
                        "content_hash": digest(row["content"]),
                    },
                    sid,
                )
                create(
                    db,
                    "passage",
                    "curation",
                    {
                        "source_id": sid,
                        "locator": row["locator"],
                        "content": row["content"],
                        "text_hash": digest(row["content"]),
                        "language": "zh-Hant",
                        "span": [0, len(row["content"])],
                    },
                    pid,
                )
                create(
                    db,
                    "claim",
                    "curation",
                    {
                        "text": row["text"],
                        "horse_name": row["horse_name"],
                        "source_id": sid,
                        "passage_id": pid,
                        "passage_version": 1,
                        "epistemic_status": row["epistemic_status"],
                        "evidence_strength": "MODERATE",
                        "relation": "SUPPORTS",
                        "review_state": "DRAFT",
                    },
                    cid,
                )
            db.commit()
    print("V2 initialized. Existing legacy data is retained. Evidence examples remain DRAFT.")
elif args.command == "api":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, log_level="warning")
else:
    from app.v2.runtime import main

    main()
