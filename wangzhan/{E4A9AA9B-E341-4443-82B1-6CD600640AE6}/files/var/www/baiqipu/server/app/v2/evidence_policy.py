"""Evidence-use policy: verifiable quotation is independent from expert approval."""

from datetime import datetime, timezone

from .domain import digest
from .models import Entity
from .source_acquisition import link_alias, validate_document, work_policy


def machine_quotation(repo, claim, source, passage):
    c, s, p = claim.data, source.data, passage.data
    if (
        c.get("presentation_track") != "AUTO_VERIFIED_SOURCE"
        or c.get("machine_validation") != "VERIFIED_QUOTATION"
        or c.get("relation") != "MENTIONS"
        or c.get("entailment") != "UNVERIFIED"
        or c.get("human_review_state") != "NOT_REVIEWED"
        or s.get("rights_state") not in ("PERMITTED_REUSE", "ATTRIBUTION_REQUIRED")
        or s.get("provenance_state") != "EXACT_REVISION_MATCH"
        or s.get("acquisition_state") != "PARSED"
        or s.get("access_state") != "AVAILABLE"
    ):
        return False
    health = repo.db.get(Entity, source.id + "-health")
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(health.data["checked_at"])).total_seconds()
        if repo.snapshot_only:
            # Explicit archive browsing only; never renews current citation eligibility.
            if health.data["status"] not in ("AVAILABLE", "TEMPORARY_NETWORK_ERROR") or age < 0:
                return False
        elif health.data["status"] != "AVAILABLE" or not 0 <= age <= 7 * 86400:
            return False
    except (AttributeError, KeyError, ValueError, TypeError):
        return False
    key = s.get("document_id")
    if key not in repo.document_checks:
        document = repo.db.get(Entity, key) if key else None
        doc = (
            {k: v for k, v in document.data.items() if k != "visibility"}
            if document and document.kind == "source_document"
            else {}
        )
        repo.document_checks[key] = (doc, validate_document(doc))
    doc, valid = repo.document_checks[key]
    if not valid or digest(doc) != s.get("document_hash"):
        return False
    if (
        doc["revision_id"] != s.get("upstream_revision")
        or doc["title"] != s.get("title")
        or s.get("url") != f"https://zh.wikisource.org/w/index.php?oldid={doc['revision_id']}"
        or s.get("license_url") != doc["rights"]["url"]
        or s.get("kind") != work_policy(doc["title"])[0]
        or s.get("content_hash") != digest(doc["text"])
    ):
        return False
    expected_edition = f"維基文庫 oldid={doc['revision_id']}; render={doc['html_hash'][:16]}; {doc['parser']}"
    if s.get("edition") != expected_edition:
        return False
    match = next(
        (r for r in doc["paragraphs"] if r["locator"] == p.get("locator") and r["offset"] == p.get("document_offset")),
        None,
    )
    if (
        not match
        or match["text"] != p.get("content")
        or c.get("span") != [0, len(match["text"])]
        or doc["text"][match["offset"][0] : match["offset"][1]] != match["text"]
    ):
        return False
    subjects = repo.subjects(claim)
    if not subjects:
        return False
    for identity in subjects:
        row = next((r for r in repo.editorial if r["id"] == identity), None)
        entity = repo.rows.get(identity)
        if entity and entity.kind == "knowledge_entity" and repo.public(entity):
            row = {"id": identity, **entity.data}
        if not row or link_alias(row, match["text"], doc["title"]) != c.get("entity_alias"):
            return False
    return True
