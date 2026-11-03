"""Package a complete, runnable delivery bundle.

The bundle is a drop-in copy of the working tree:

  * every git-tracked file at its real path (so `scripts/paths.py` resolves)
  * the gitignored runtime state that makes the site runnable with data
  * the gitignored deliverables (sample MP4/SRT/PNG) and screenshots
  * a MANIFEST.json with a sha256 for every packaged file
  * a README_交付总览.md entry point

Secrets are the local development secret only; no production credential and
no original-site `.env` is included.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "百骑谱V2_完整交付包"

# Gitignored runtime state that belongs in the bundle so the site runs with data.
RUNTIME_INCLUDE = [
    "runtime/steedatlas.db",
    "runtime/backups/legacy.db",
    "runtime/demo-inputs",
    "runtime/development-secret.txt",
    "runtime/media",
]

# Gitignored report artefacts that belong in the bundle.
EXTRA_INCLUDE = [
    "deliverables",
    "reports/screenshots",
]

EXCLUDE_SUFFIX = {".pyc", ".pyo"}
EXCLUDE_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".git"}


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    return result.stdout.decode("utf-8", errors="replace")


def tracked_files() -> list[str]:
    out = git("ls-files", "-z")
    return [p for p in out.split("\0") if p]


def collect_extra() -> list[str]:
    found: list[str] = []
    for rel in EXTRA_INCLUDE:
        target = ROOT / rel
        if not target.exists():
            continue
        if target.is_file():
            found.append(rel)
            continue
        for base, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for name in files:
                if name.endswith(tuple(EXCLUDE_SUFFIX)):
                    continue
                full = Path(base) / name
                found.append(full.relative_to(ROOT).as_posix())
    return found


def collect_runtime() -> list[str]:
    found: list[str] = []
    for rel in RUNTIME_INCLUDE:
        target = ROOT / rel
        if not target.exists():
            print(f"  [skip] {rel} (not present)")
            continue
        if target.is_file():
            found.append(rel)
            continue
        for base, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for name in files:
                if name.endswith(tuple(EXCLUDE_SUFFIX)):
                    continue
                full = Path(base) / name
                found.append(full.relative_to(ROOT).as_posix())
    return found


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT.parent / f"{PREFIX}_20261101.zip"))
    parser.add_argument("--readme", default=str(ROOT / "docs" / "README_交付总览.md"))
    args = parser.parse_args()

    entries: dict[str, Path] = {}

    for rel in tracked_files():
        source = ROOT / rel
        if source.is_file():
            entries[rel] = source

    for rel in collect_extra() + collect_runtime():
        source = ROOT / rel
        if source.is_file():
            entries.setdefault(rel, source)

    print(f"[delivery] packaging {len(entries)} files")

    manifest = {
        "package": PREFIX,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": "baiqipu-github",
        "branch": git("branch", "--show-current").strip(),
        "head": git("rev-parse", "HEAD").strip(),
        "file_count": len(entries),
        "contents": {
            "source": "all git-tracked files at their real paths",
            "runtime": "gitignored local runtime state (DB, media, dev secret) so the site runs with data",
            "deliverables": "gitignored sample MP4/SRT/PNG and verification screenshots",
        },
        "not_included": [
            ".venv/ (recreate with pip install -r requirements-dev.txt)",
            "frontend/node_modules/ (recreate with npm ci)",
            "production .env and any real credential",
            "*.log and PID files",
        ],
        "files": [],
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in sorted(entries):
            source = entries[rel]
            arc = f"{PREFIX}/{rel}"
            zf.write(source, arc)
            manifest["files"].append(
                {
                    "path": rel,
                    "bytes": source.stat().st_size,
                    "sha256": sha256(source),
                }
            )

        readme = Path(args.readme)
        if readme.is_file():
            zf.write(readme, f"{PREFIX}/README_交付总览.md")
            manifest["files"].append(
                {
                    "path": "README_交付总览.md",
                    "bytes": readme.stat().st_size,
                    "sha256": sha256(readme),
                }
            )

        manifest["files"].sort(key=lambda item: item["path"])
        manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        zf.writestr(f"{PREFIX}/MANIFEST.json", manifest_bytes)

    print(f"[delivery] wrote {out_path}")
    print(f"[delivery] bytes = {out_path.stat().st_size}")
    print(f"[delivery] sha256 = {sha256(out_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
