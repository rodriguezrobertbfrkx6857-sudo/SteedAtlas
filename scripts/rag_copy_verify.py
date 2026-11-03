"""Exercise expansion and rollback on a unique online backup; original DB is read only."""

import json
import os
import sqlite3
import subprocess
import sys
import time

from paths import ROOT, SERVER

source = ROOT / "runtime/steedatlas.db"
target = ROOT / f"runtime/rag-demo-{time.time_ns()}.db"
with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src, sqlite3.connect(target) as dst:
    src.backup(dst)


def legacy_digest(path):
    import hashlib

    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        tables = [
            r[0]
            for r in db.execute("select name from sqlite_master where type='table'")
            if not r[0].startswith("v2_") and r[0] != "alembic_version"
        ]
        return {
            t: hashlib.sha256(
                repr(sorted(db.execute('select * from "' + t + '"').fetchall(), key=repr)).encode()
            ).hexdigest()
            for t in tables
        }


before = legacy_digest(source)
env = {
    **os.environ,
    "DATABASE_URL": "sqlite:///" + target.as_posix(),
    "DEBUG": "false",
    "SECRET_KEY": "copy-only-" + "a" * 48,
    "STEEDATLAS_ROOT": str(ROOT),
}
steps = []
for command in [("upgrade", "head"), ("upgrade", "head"), ("downgrade", "a8d4e7f9c201"), ("upgrade", "head")]:
    # Downgrade is destructive only to this newly created disposable copy; original remains intact.
    r = subprocess.run([sys.executable, "-m", "alembic", *command], cwd=SERVER, env=env, capture_output=True)
    assert r.returncode == 0, r.stderr.decode(errors="replace")
    assert legacy_digest(target) == before
    steps.append({"command": list(command), "exit_code": r.returncode, "legacy_rows_identical": True})
# Restore V2 state into a separate copy for demo; no rollback of original data.
demo = ROOT / f"runtime/rag-live-{time.time_ns()}.db"
with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src, sqlite3.connect(demo) as dst:
    src.backup(dst)
r = subprocess.run(
    [sys.executable, str(ROOT / "scripts/rag_migrate.py"), "--database", str(demo.relative_to(ROOT)), "--apply"],
    capture_output=True,
)
assert r.returncode == 0, r.stderr.decode(errors="replace")
r2 = subprocess.run(
    [sys.executable, str(ROOT / "scripts/rag_migrate.py"), "--database", str(demo.relative_to(ROOT)), "--apply"],
    capture_output=True,
)
assert r2.returncode == 0
second = json.loads(r2.stdout.decode("utf-8") if os.environ.get("PYTHONUTF8") else r2.stdout.decode(errors="replace"))
assert second["actions"] == []
assert legacy_digest(demo) == before == legacy_digest(source)
(ROOT / "runtime/rag-demo-path.txt").write_text(str(demo.relative_to(ROOT)), encoding="utf-8")
report = {
    "scope": "UNIQUE_COPIES_ONLY",
    "legacy_row_digests": before,
    "steps": steps,
    "idempotent": True,
    "original_unchanged": True,
    "demo_database": str(demo.relative_to(ROOT)),
}
(ROOT / "reports/rag-upgrade/migration.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("Copy migration, idempotence, rollback and exact legacy-row preservation PASS")
