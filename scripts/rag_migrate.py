"""Expand-only, repeatable knowledge linking. Default dry run; never deletes data."""

import argparse
import json
import os
import sys

from paths import ROOT, SERVER


def migrate(db, apply=False):
    from app.routers.horses import _build_rag_library_items
    from app.v2.domain import create, revise
    from app.v2.models import Entity
    from sqlalchemy import select

    rows = _build_rag_library_items(db)
    aliases = {"chitu": ["赤菟", "赤兔马"], "wuzhui": ["烏騅", "骓"], "dilu": ["的盧", "的颅"]}
    actions = []
    for row in rows:
        if not db.get(Entity, row["id"]):
            actions.append({"action": "entity", "id": row["id"]})
            if apply:
                create(
                    db,
                    "knowledge_entity",
                    "curation",
                    {
                        "name": row["name"],
                        "entity_type": "Horse",
                        "aliases": aliases.get(row["id"], []),
                        "visibility": "PUBLIC",
                    },
                    row["id"],
                )
    for c in db.scalars(select(Entity).where(Entity.kind == "claim")).all():
        if c.data.get("subject_entity_ids"):
            continue
        matches = [r["id"] for r in rows if r["name"] == c.data.get("horse_name")]
        if len(matches) == 1:
            actions.append({"action": "link", "id": c.id, "subjects": matches})
            if apply:
                # Association changes do not grant approval; reviewed legacy claims need re-review.
                revise(
                    db,
                    c,
                    c.version,
                    {**c.data, "horse_id": matches[0], "subject_entity_ids": matches, "review_state": "DRAFT"},
                    "knowledge-migration",
                )
                from app.v2.api import _invalidate_claim

                _invalidate_claim(db, c.id, "knowledge-migration")
    if apply:
        db.commit()
    return {
        "mode": "APPLY" if apply else "DRY_RUN",
        "actions": actions,
        "editorial_profiles": len(rows),
        "policy": "Legacy text remains EDITORIAL; creative fields are not evidence",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--database", default="runtime/steedatlas.db")
    args = parser.parse_args()
    path = (ROOT / args.database).resolve()
    if not path.is_relative_to(ROOT.resolve()) or not path.exists():
        raise SystemExit("Existing project-owned database required")
    os.environ.update(
        DATABASE_URL="sqlite:///" + path.as_posix(),
        DEBUG="false",
        SECRET_KEY="offline-migration-" + "x" * 48,
        STEEDATLAS_ROOT=str(ROOT),
    )
    sys.path.insert(0, str(SERVER))
    from app.database import SessionLocal

    with SessionLocal() as db:
        print(json.dumps(migrate(db, args.apply), ensure_ascii=False, indent=2))
