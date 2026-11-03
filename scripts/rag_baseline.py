"""Read-only inventory, SQLite online backups and private checksums. Never print secrets."""

import hashlib
import json
import shutil
import sqlite3
import time

from paths import ROOT, SERVER


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    target = ROOT / "runtime/backups" / ("rag-" + str(time.time_ns()))
    target.mkdir(parents=True)
    files = [
        ROOT / "runtime/steedatlas.db",
        ROOT / "runtime/development-secret.txt",
        ROOT / "reports/original-video-factory-v2.json",
    ]
    files += list(SERVER.glob(".env*")) + list((SERVER / "data").glob("*.json"))
    manifest = []
    counts = {}
    for index, path in enumerate(files):
        if not path.is_file():
            continue
        dest = target / (str(index) + "-" + path.name)
        if path.suffix == ".db":
            with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as src, sqlite3.connect(dest) as dst:
                src.backup(dst)
                for (table,) in src.execute("select name from sqlite_master where type='table'"):
                    counts[table] = src.execute('select count(*) from "' + table.replace('"', '""') + '"').fetchone()[0]
        else:
            shutil.copy2(path, dest)
        manifest.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path), "backup_sha256": sha(dest)})
    for folder in [ROOT / "runtime", SERVER / "generated"]:
        for path in folder.rglob("*") if folder.exists() else []:
            if path.suffix.lower() in {".mp4", ".srt", ".wav", ".png", ".jpg"} and "backups" not in path.parts:
                manifest.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path), "retained_in_place": True})
    (target / "private-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    out = ROOT / "reports/rag-upgrade"
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "backup": str(target.relative_to(ROOT)),
        "protected_file_count": len(manifest),
        "legacy_table_counts": counts,
        "media_policy": "hashed and retained in place; no writes",
        "initial_dirty_file": "reports/original-video-factory-v2.json",
        "initial_head": "5359141",
        "synced_head": "e30acf7",
        "remote_main": "9f98765",
    }
    (out / "baseline.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
