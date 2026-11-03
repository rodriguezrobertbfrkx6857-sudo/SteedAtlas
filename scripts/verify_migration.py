"""Test upgrade/downgrade/upgrade only on a fresh copy of the protected backup."""

import json
import os
import sqlite3
import subprocess
import sys

from paths import ROOT, SERVER

source = ROOT / "runtime/backups/legacy.db"
copy_path = ROOT / "runtime/migration-verification.db"
if copy_path.exists():
    raise SystemExit("Verification DB already exists; preserve it and use a fresh filename")
c = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
out = sqlite3.connect(copy_path)
c.backup(out)
out.close()
c.close()
env = {**os.environ, "DATABASE_URL": "sqlite:///" + copy_path.as_posix(), "DEBUG": "false"}


def counts():
    with sqlite3.connect(copy_path) as c:
        tables = [
            r[0]
            for r in c.execute("select name from sqlite_master where type='table'")
            if not r[0].startswith("v2_") and r[0] != "alembic_version"
        ]
        return {t: c.execute('select count(*) from "' + t + '"').fetchone()[0] for t in tables}


before = counts()
runs = []
for command in [("upgrade", "head"), ("downgrade", "a8d4e7f9c201"), ("upgrade", "head")]:
    p = subprocess.run([sys.executable, "-m", "alembic", *command], cwd=SERVER, env=env, capture_output=True)
    runs.append({"command": list(command), "returncode": p.returncode, "stderr": p.stderr.decode(errors="replace")})
    assert p.returncode == 0, runs[-1]
    assert counts() == before
result = {
    "mode": "LOCAL_COPY_ONLY",
    "legacy_counts_before": before,
    "legacy_counts_after": counts(),
    "runs": runs,
    "preserved": True,
}
(ROOT / "reports/migration-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print("Legacy table counts preserved through upgrade/downgrade/upgrade")
