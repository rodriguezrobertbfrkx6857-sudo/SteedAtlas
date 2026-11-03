"""CC0 metadata for unresolved identities; never historical passage evidence."""

import re

from .domain import create, digest, revise
from .models import Entity
from .source_acquisition import AcquisitionError, WikisourceProvider


class WikidataProvider(WikisourceProvider):
    api_url = "https://www.wikidata.org/w/api.php"

    def candidates(self, entity):
        found = self.request({"action": "wbsearchentities", "search": entity["name"], "language": "zh", "limit": 3})
        ids = [r["id"] for r in found.get("search", []) if re.fullmatch(r"Q[1-9][0-9]*", r.get("id", ""))]
        if not ids:
            return []
        result = self.request(
            {
                "action": "wbgetentities",
                "ids": "|".join(ids),
                "languages": "zh|en|zh-hans|zh-hant",
                "props": "labels|descriptions|aliases|claims|info",
            }
        )
        rows = []
        for qid in ids:
            data = result["entities"].get(qid, {})
            if data.get("missing") is not None or not data.get("lastrevid"):
                continue
            rows.append(
                {
                    "catalogue_id": entity["id"],
                    "query_name": entity["name"],
                    "qid": qid,
                    "revision": data["lastrevid"],
                    "source_url": f"https://www.wikidata.org/w/index.php?oldid={data['lastrevid']}",
                    "labels": data.get("labels", {}),
                    "aliases": data.get("aliases", {}),
                    "descriptions": data.get("descriptions", {}),
                    "statements": data.get("claims", {}),
                    "response_hash": digest(data),
                    "license": "CC0-1.0",
                    "rights_evidence_url": "https://www.wikidata.org/wiki/Wikidata:Licensing",
                    "identity_match": "UNRESOLVED",
                    "historical_evidence": False,
                    "provenance_state": "EXACT_REVISION_MATCH",
                    "machine_validation": "AUTOMATED_ATTRIBUTION",
                    "human_review_state": "NOT_REVIEWED",
                    "visibility": "PUBLIC",
                }
            )
        return rows


def store_candidates(db, rows, apply=False):
    actions = []
    for row in rows:
        if (
            row.get("license") != "CC0-1.0"
            or row.get("historical_evidence") is not False
            or row.get("identity_match") != "UNRESOLVED"
        ):
            raise AcquisitionError("INVALID_ENTITY_CANDIDATE")
        identity = "wdc-" + digest([row["catalogue_id"], row["qid"]])[:40]
        old = db.get(Entity, identity)
        changed = old is None or old.data != row
        if apply and changed:
            if old:
                revise(db, old, old.version, row, "wikidata-discovery")
            else:
                create(db, "entity_candidate", "wikidata-discovery", row, identity)
        actions.append({"id": identity, "qid": row["qid"], "revision": row["revision"], "changed": changed})
    return actions
