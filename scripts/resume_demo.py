"""RC entry point: empty DB initialization, pinned replay, isolated local services."""

import argparse
import json
import os
import socket
import subprocess
import sys
import time

from paths import ROOT, SERVER
from resume_demo_preflight import owned


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "seed-demo", "replay", "start", "stop"])
    parser.add_argument("--database", default="runtime/resume-rc/autonomous-demo.db")
    parser.add_argument("--cache", default="runtime/source-cache")
    parser.add_argument("--manifest", default="reports/rag-upgrade/autonomous/source-manifest.json")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--max-pages", type=int, default=6)
    parser.add_argument("--report", default="reports/resume-readiness/replay.json")
    args = parser.parse_args()
    path, cache, manifest, report_path = map(owned, (args.database, args.cache, args.manifest, args.report))
    if not path.is_relative_to(ROOT / "runtime") or not path.name.startswith("autonomous-"):
        raise SystemExit("Use a project runtime/autonomous-*.db isolated demo file")
    if not 1 <= args.max_pages <= 30 or (args.offline and args.refresh):
        raise SystemExit("Invalid bounded replay options")
    if args.command == "init":
        if path.exists():
            raise SystemExit("Database already exists; refusing overwrite. Use replay/start.")
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, str(ROOT / "scripts/run_v2.py"), "init", "--database", str(path)], check=True)
    if not path.is_file():
        raise SystemExit("Run init first; no original user database is required or copied")
    os.environ.update(
        DATABASE_URL="sqlite:///" + path.as_posix(),
        SECRET_KEY="rc-local-pipeline-" + "x" * 48,
        DEBUG="false",
        STEEDATLAS_ROOT=str(ROOT),
    )
    if args.command in ("init", "seed-demo"):
        sys.path.insert(0, str(SERVER))
        from app.database import SessionLocal
        from app.models.horse import Horse
        from app.models.product import Product
        from app.routers.horses import _build_rag_library_items
        from rag_migrate import migrate

        with SessionLocal() as db:
            for row in _build_rag_library_items(db):
                if not db.get(Horse, row["id"]):
                    fields = {k: v for k, v in row.items() if k in Horse.__table__.columns.keys()}
                    db.add(Horse(**fields))
            db.flush()
            if not db.get(Product, "resume-demo-chitu"):
                db.add(
                    Product(
                        id="resume-demo-chitu",
                        name="演示商品·赤兔书签（沙箱无实物）",
                        horse_id="chitu",
                        price=9.9,
                        stock=100,
                        description="发布候选测试数据；没有真实交易、配送或库存承诺。",
                        images=[],
                    )
                )
            db.commit()
            print(json.dumps(migrate(db, True), ensure_ascii=False))
        return
    if args.command == "replay":
        sys.path.insert(0, str(SERVER))
        from app.database import SessionLocal
        from app.v2.domain import digest
        from app.v2.knowledge import KnowledgeRepository
        from app.v2.source_acquisition import AcquisitionError, WikisourceProvider, ingest_document, mark_unavailable

        provider = WikisourceProvider(cache, max_requests=min(90, args.max_pages * 3), offline=args.offline)
        report = {"database": str(path.relative_to(ROOT)), "offline": args.offline, "imports": [], "blocked": []}
        try:
            with SessionLocal() as db:
                repo = KnowledgeRepository(db)
                catalogue = [
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "aliases": repo.rows[r["id"]].data.get("aliases", []) if r["id"] in repo.rows else [],
                    }
                    for r in repo.editorial
                ]
                for item in json.loads(manifest.read_text(encoding="utf-8"))["sources"][: args.max_pages]:
                    try:
                        doc = provider.fetch(item["title"], refresh=args.refresh, revision=item["upstream_revision"])
                        if digest({k: v for k, v in doc.items() if k != "checked_at"}) != item["document_hash"]:
                            raise AcquisitionError("MANIFEST_SNAPSHOT_MISMATCH")
                        with db.begin_nested():
                            result = ingest_document(db, doc, catalogue, True)
                        db.commit()
                        report["imports"].append(result)
                    except (AcquisitionError, KeyError, ValueError) as exc:
                        db.rollback()
                        report["blocked"].append({"title": item["title"], "reason": str(exc)})
                        if not args.offline and str(exc) != "REQUEST_BUDGET":
                            mark_unavailable(db, item["title"], str(exc))
                report["coverage"] = KnowledgeRepository(db).coverage()
        finally:
            report["trace"] = provider.trace
            report["network_requests"] = provider.calls
            provider.close()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: report[k] for k in ("blocked", "coverage", "network_requests")}, ensure_ascii=False))
        return 2 if report["blocked"] else 0
    state = path.parent / "services.json"
    if args.command == "stop":
        if not state.exists():
            raise SystemExit("No owned service record")
        # Check command line and creation time before stopping any recorded PID.
        records = json.loads(state.read_text())["processes"]
        for record in records:
            command = (
                "$p=Get-CimInstance Win32_Process -Filter 'ProcessId="
                + str(record["pid"])
                + "'; if($p -and $p.CreationDate.ToUniversalTime().ToString('o') -eq '"
                + record["created"]
                + "'){ Stop-Process -Id $p.ProcessId }"
            )
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command], check=True)
        print("Stopped only matching processes recorded by this launcher; state retained.")
        return
    for port in (8006, 5178):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                raise SystemExit(f"Port {port} occupied; no other process will be killed")
    node = ROOT / "frontend/node_modules/vite/bin/vite.js"
    if not node.exists():
        raise SystemExit("Run npm.cmd --prefix frontend ci first")
    env = {**os.environ, "STEEDATLAS_RC_API": "http://127.0.0.1:8006", "STEEDATLAS_RC_PORT": "5178"}
    python = sys.executable
    commands = [
        [python, str(ROOT / "scripts/run_v2.py"), "api", "--database", str(path), "--port", "8006"],
        [python, str(ROOT / "scripts/run_v2.py"), "worker", "--database", str(path)],
        ["node", str(node), "--config", str(ROOT / "frontend/vite.config.ts"), "--mode", "resume-rc"],
    ]
    records = []
    for name, command in zip(("api", "worker", "web"), commands):
        with (path.parent / (name + ".log")).open("ab") as log:
            proc = subprocess.Popen(
                command,
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        created = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-CimInstance Win32_Process -Filter 'ProcessId={proc.pid}').CreationDate.ToUniversalTime().ToString('o')",
            ],
            text=True,
        ).strip()
        records.append({"name": name, "pid": proc.pid, "created": created})
        child_json = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"@(Get-CimInstance Win32_Process -Filter 'ParentProcessId={proc.pid}' | ForEach-Object {{ @{{pid=$_.ProcessId; created=$_.CreationDate.ToUniversalTime().ToString('o')}} }}) | ConvertTo-Json -Compress",
            ],
            text=True,
        ).strip()
        children = json.loads(child_json) if child_json else []
        for child in children if isinstance(children, list) else [children]:
            records.append({"name": name + "-child", **child})
        state.write_text(json.dumps({"database": str(path), "api": 8006, "web": 5178, "processes": records}, indent=2))
    for _ in range(30):
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", 8006)) == 0:
                print("Original black/gold site: http://127.0.0.1:5178 ; API:8006 ; same isolated DB for API/Worker")
                return
        time.sleep(1)
    raise SystemExit("API did not become ready; see isolated logs and run stop")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
