"""Bounded CC0 entity metadata discovery; no automatic same-as or fact assertions."""

import argparse
import json
import os
import sys

from paths import ROOT, SERVER

sys.stdout.reconfigure(encoding="utf-8")
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--entities", default="chitu,wuzhui,dilu")
parser.add_argument("--apply", action="store_true")
parser.add_argument("--offline", action="store_true")
args = parser.parse_args()
path = (ROOT / (ROOT / "runtime/autonomous-demo-path.txt").read_text().strip()).resolve()
if not path.is_relative_to(ROOT / "runtime") or not path.name.startswith("autonomous-"):
    raise SystemExit("Isolated project database required")
os.environ.update(
    DATABASE_URL="sqlite:///" + path.as_posix(),
    DEBUG="false",
    SECRET_KEY="offline-wd-" + "x" * 48,
    STEEDATLAS_ROOT=str(ROOT),
)
sys.path.insert(0, str(SERVER))
from app.database import SessionLocal
from app.v2.knowledge import KnowledgeRepository
from app.v2.source_acquisition import AcquisitionError
from app.v2.wikidata_discovery import WikidataProvider, store_candidates

provider = WikidataProvider(ROOT / "runtime/wikidata-cache", max_requests=12, offline=args.offline)
report = {
    "mode": "APPLY" if args.apply else "DRY_RUN",
    "entities": [],
    "policy": "CC0_METADATA_ONLY_NO_AUTOMATIC_IDENTITY_MERGE",
}
with SessionLocal() as db:
    catalogue = KnowledgeRepository(db).editorial
    for entity in [e for e in catalogue if e["id"] in args.entities.split(",")][:6]:
        try:
            rows = provider.candidates(entity)
            actions = store_candidates(db, rows, args.apply)
            if args.apply:
                db.commit()
            report["entities"].append({"horse_id": entity["id"], "candidates": rows, "actions": actions})
            print(
                json.dumps({"horse_id": entity["id"], "candidate_qids": [r["qid"] for r in rows]}, ensure_ascii=False),
                flush=True,
            )
        except AcquisitionError as exc:
            report["entities"].append({"horse_id": entity["id"], "status": "BLOCKED", "reason": str(exc)})
provider.close()
report["trace"] = provider.trace
(ROOT / "reports/rag-upgrade/autonomous/wikidata-candidates.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
