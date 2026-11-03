"""Bounded official-API acquisition. Public quotation verification, never fact approval.

Only ancient original works in the explicit rights/genre allowlist are copied.
Modern translations, search snippets and dataset-card licence guesses are excluded.
Raw API snapshots are immutable private source_document records; citations point
to character offsets in the deterministic extracted text, not to normalized text.
"""

import hashlib
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup
from opencc import OpenCC

from .domain import create, digest, revise
from .models import Entity

API = "https://zh.wikisource.org/w/api.php"
UA = "SteedAtlasEvidence/0.1 (https://github.com/rodriguezrobertbfrkx6857-sudo/baiqipu; source attribution)"
LICENSE = "https://creativecommons.org/licenses/by-sa/4.0/"
PARSER = "mediawiki-paragraphs-v1"
T2S, S2T = OpenCC("t2s"), OpenCC("s2t")
# Work classification is a routing/rights policy, not a historical claim.
WORKS = {
    "三國志": ("PRIMARY_RECORD", "陳壽；含裴松之注", "3–5世紀"),
    "史記": ("PRIMARY_RECORD", "司馬遷", "前1世紀"),
    "漢書": ("PRIMARY_RECORD", "班固等", "1–2世紀"),
    "後漢書": ("PRIMARY_RECORD", "范曄等", "5世紀"),
    "晉書": ("PRIMARY_RECORD", "房玄齡等", "7世紀"),
    "舊唐書": ("PRIMARY_RECORD", "劉昫等", "10世紀"),
    "新唐書": ("PRIMARY_RECORD", "歐陽修、宋祁等", "11世紀"),
    "周書": ("PRIMARY_RECORD", "令狐德棻等", "7世紀"),
    "北史": ("PRIMARY_RECORD", "李延壽", "7世紀"),
    "南史": ("PRIMARY_RECORD", "李延壽", "7世紀"),
    "梁書": ("PRIMARY_RECORD", "姚思廉", "7世紀"),
    "資治通鑑": ("PRIMARY_RECORD", "司馬光等", "11世紀"),
    "三國演義": ("LITERARY_WORK", "羅貫中", "14世紀"),
    "水滸傳": ("LITERARY_WORK", "施耐庵（傳）", "14–16世紀"),
    "西遊記": ("LITERARY_WORK", "吳承恩（傳）", "16世紀"),
    "隋唐演義": ("LITERARY_WORK", "褚人穫", "17世紀"),
    "封神演義": ("LITERARY_WORK", "許仲琳（傳）", "16世紀"),
    "穆天子傳": ("LITERARY_WORK", "佚名", "先秦至晉代傳本"),
    "拾遺記": ("LITERARY_WORK", "王嘉等", "4–6世紀"),
    "述異記": ("LITERARY_WORK", "傳本作者有異", "中古傳本"),
    "太平御覽": ("PRIMARY_RECORD", "李昉等", "10世紀"),
    "世說新語": ("LITERARY_WORK", "劉義慶等", "5世紀"),
    "名馬記": ("PRIMARY_RECORD", "郭子章", "明代"),
    "全唐詩": ("LITERARY_WORK", "彭定求等編；各篇作者見原文", "1707年編成"),
    "水滸傳 (120回本)": ("LITERARY_WORK", "施耐庵、羅貫中（傳）", "明代傳本"),
    "說唐": ("LITERARY_WORK", "佚名", "清代"),
    "太平廣記": ("LITERARY_WORK", "李昉等編", "10世紀"),
}
SEEDS = {
    "chitu": ["三國志/卷07", "三國演義/第003回"],
    "wuzhui": ["史記/卷007"],
    "dilu": ["三國志/卷32", "三國演義/第034回"],
    "jueying": ["三國志/卷01", "名馬記/卷上", "名馬記/卷下"],
}


def normalized(value):
    return T2S.convert(value).replace("赤菟", "赤兔").replace("的颅", "的卢")


def work_policy(title):
    work = title.split("/")[0]
    return WORKS.get(work) if not any(x in title for x in ("翻譯", "译", "譯", "白話", "校注")) else None


def extract_paragraphs(html):
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".mw-parser-output") or soup
    for node in root.select("script,style,table,.mw-editsection,.reference,.noprint,.navbox,.toc"):
        node.decompose()
    paragraphs, offset, section = [], 0, "正文"
    for node in root.find_all(["h2", "h3", "p"]):
        text = node.get_text().strip()
        if node.name != "p":
            section = text
        elif text:
            locator = f"{section} / 段{len(paragraphs) + 1}"
            paragraphs.append({"text": text, "locator": locator, "offset": [offset, offset + len(text)]})
            offset += len(text) + 1
    return paragraphs


def aliases_for(entity):
    names = [entity["name"], *entity.get("aliases", [])]
    # Single-character 骓 is only accepted in the explicitly targeted Shiji chapter.
    return sorted({normalized(n) for n in names if len(n) >= 2})


def link_alias(entity, text, title):
    value = normalized(text)
    # Catalogue h015 is specifically Tang Sanzang's fictional horse. The same
    # spelling in Sui/Tang narratives is not evidence for that identity.
    if entity["id"] == "h015" and normalized(title.split("/")[0]) != "西游记":
        return None
    matches = []
    ambiguous = {"虎步", "龙骧", "飞黄", "骐骥", "绝地", "翻羽", "越影", "超光", "腾雾", "玄驹", "白义"}
    for alias in aliases_for(entity):
        for match in re.finditer(re.escape(alias), value):
            context = value[max(0, match.start() - 70) : match.end() + 70]
            if not any(x in context for x in ("马", "驹", "骏", "骥", "骑", "骖", "鞍", "辔", "骢", "騧", "骊", "骝")):
                continue
            if alias in ambiguous and not re.search(
                r"(?:名[曰为]?|曰|号)[^。，；：]{0,5}" + re.escape(alias),
                value[max(0, match.start() - 10) : match.end()],
            ):
                continue
            matches.append(alias)
    if entity["id"] == "wuzhui" and title == "史記/卷007" and "騅" in text and "馬" in text:
        matches.append("骓")
    # A bare repeated name is an attributed mention only, not identity/ownership proof.
    return matches[0] if matches else None


class AcquisitionError(ValueError):
    pass


def mark_unavailable(db, title, reason):
    from sqlalchemy import select

    from .knowledge_api import invalidate_dependents

    for source in db.scalars(select(Entity).where(Entity.kind == "source")):
        if source.data.get("title") == title and source.data.get("provider") == "wikisource":
            health = db.get(Entity, source.id + "-health")
            if health:
                revise(
                    db,
                    health,
                    health.version,
                    {
                        **health.data,
                        "status": "TEMPORARY_NETWORK_ERROR"
                        if reason == "TEMPORARY_NETWORK_ERROR"
                        or reason == "MEDIAWIKI_maxlag"
                        or reason.startswith(("HTTP_429", "HTTP_503", "HTTP_502"))
                        else "UNAVAILABLE",
                        "reason": reason[:200],
                        "last_attempt_at": datetime.now(timezone.utc).isoformat(),
                    },
                    "source-pipeline",
                )
            invalidate_dependents(db, source.id, "source-pipeline")
    db.commit()


class WikisourceProvider:
    api_url = API

    def __init__(self, cache, max_requests=30, delay=1.0, timeout=12, offline=False):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.max_requests, self.delay, self.timeout = max_requests, max(1, delay), timeout
        self.offline, self.calls, self.trace = offline, 0, []
        self.last = 0
        self.observed = []
        self.client = httpx.Client(timeout=timeout, headers={"User-Agent": UA}, follow_redirects=False)

    def close(self):
        self.client.close()

    def request(self, params, refresh=False):
        import json

        params = {"format": "json", "formatversion": 2, "maxlag": 5, **params}
        path = self.cache / (digest(params) + ".json")
        # Cached observations expire; --offline is explicit reproducible snapshot replay.
        if path.exists() and not refresh and (self.offline or time.time() - path.stat().st_mtime < 86400):
            result = json.loads(path.read_text(encoding="utf-8"))
            self.observed.append(path.stat().st_mtime)
            self.trace.append({"params": params, "status": "CACHE", "hash": digest(result)})
            return result
        if self.offline or self.calls >= self.max_requests:
            raise AcquisitionError("OFFLINE_CACHE_MISS" if self.offline else "REQUEST_BUDGET")
        time.sleep(max(0, self.delay - (time.monotonic() - self.last)))
        self.calls += 1
        self.last = time.monotonic()
        try:
            r = self.client.get(self.api_url, params=params)
            if r.status_code != 200:
                raise AcquisitionError(f"HTTP_{r.status_code}; no bypass/retry storm")
            if len(r.content) > 4_000_000:
                raise AcquisitionError("RESPONSE_SIZE_LIMIT")
            result = r.json()
            if "error" in result:
                raise AcquisitionError("MEDIAWIKI_" + result["error"].get("code", "ERROR"))
            path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            self.observed.append(path.stat().st_mtime)
            self.trace.append({"params": params, "status": "FETCHED", "hash": digest(result)})
            return result
        except (httpx.HTTPError, ValueError) as exc:
            self.trace.append(
                {"params": params, "status": "FAILED", "reason": type(exc).__name__ + ": " + str(exc)[:160]}
            )
            raise AcquisitionError(
                "TEMPORARY_NETWORK_ERROR" if isinstance(exc, httpx.HTTPError) else "INVALID_RESPONSE"
            ) from exc

    def discover(self, entity, limit=3):
        name = S2T.convert(entity["name"])
        result = self.request(
            {
                "action": "query",
                "list": "search",
                "srnamespace": 0,
                "srsearch": '"' + name + '" -intitle:判决 -intitle:裁定',
                "srlimit": min(limit, 5),
                "srprop": "",
            }
        )
        return [
            {"title": r["title"], "permitted_work": bool(work_policy(r["title"])), "provider": "wikisource"}
            for r in result["query"]["search"]
        ]

    def fetch(self, title, refresh=False, revision=None):
        policy = work_policy(title)
        if not policy:
            raise AcquisitionError("QUARANTINED_WORK_EDITION_RIGHTS_UNKNOWN")
        rights = self.request({"action": "query", "meta": "siteinfo", "siprop": "rightsinfo"}, refresh)
        info = rights["query"]["rightsinfo"]
        if not info.get("url", "").startswith(LICENSE):
            raise AcquisitionError("QUARANTINED_SITE_LICENSE_CHANGED")
        revision_query = {
            "action": "query",
            "prop": "revisions",
            "rvprop": "ids|timestamp|content|sha1",
            "rvslots": "main",
        }
        if revision is not None and (not isinstance(revision, int) or revision < 1):
            raise AcquisitionError("INVALID_REVISION")
        # Prefer the pinned-revision cache produced by a fresh online replay.
        # Older caches used title keys; fallback is offline-only and still checks revid.
        revision_query.update({"revids": revision} if revision else {"titles": title})
        try:
            page_result = self.request(revision_query, refresh)
        except AcquisitionError as exc:
            if not self.offline or not revision or str(exc) != "OFFLINE_CACHE_MISS":
                raise
            revision_query.pop("revids", None)
            revision_query["titles"] = title
            page_result = self.request(revision_query, refresh)
        page = page_result["query"]["pages"][0]
        if page.get("missing") or not page.get("revisions"):
            raise AcquisitionError("SOURCE_MISSING")
        rev = page["revisions"][0]
        if page["title"] != title or (revision is not None and rev["revid"] != revision):
            raise AcquisitionError("WRONG_EDITION")
        raw = rev["slots"]["main"]["content"]
        if hashlib.sha1(raw.encode()).hexdigest() != rev["sha1"]:
            raise AcquisitionError("UPSTREAM_CHECKSUM_MISMATCH")
        parsed = self.request(
            {"action": "parse", "oldid": rev["revid"], "prop": "text|revid", "disableeditsection": 1}, refresh
        )["parse"]
        if parsed["revid"] != rev["revid"] or parsed["title"] != page["title"]:
            raise AcquisitionError("WRONG_EDITION")
        html = parsed["text"]
        parts = extract_paragraphs(html)
        if not parts:
            raise AcquisitionError("NO_PARAGRAPHS")
        # Retain both wikitext and rendered HTML: transclusions can change without a
        # page revision, so rendering hash/time are part of the edition identity.
        return {
            "provider": "wikisource",
            "page_id": page["pageid"],
            "title": page["title"],
            "revision_id": rev["revid"],
            "revision_timestamp": rev["timestamp"],
            "wikitext": raw,
            "upstream_sha1": rev["sha1"],
            "html": html,
            "html_hash": digest(html),
            "paragraphs": parts,
            "parser": PARSER,
            "text": "\n".join(p["text"] for p in parts),
            "rights": info,
            "rights_evidence_url": API
            + "?"
            + urlencode({"action": "query", "meta": "siteinfo", "siprop": "rightsinfo", "format": "json"}),
            "checked_at": datetime.fromtimestamp(min(self.observed[-3:]), timezone.utc).isoformat(),
        }


def validate_document(doc):
    try:
        return (
            doc["provider"] == "wikisource"
            and work_policy(doc["title"]) is not None
            and doc["parser"] == PARSER
            and doc["rights"]["url"].startswith(LICENSE)
            and hashlib.sha1(doc["wikitext"].encode()).hexdigest() == doc["upstream_sha1"]
            and digest(doc["html"]) == doc["html_hash"]
            and extract_paragraphs(doc["html"]) == doc["paragraphs"]
            and doc["text"] == "\n".join(p["text"] for p in doc["paragraphs"])
        )
    except (KeyError, TypeError, ValueError):
        return False


def ingest_document(db, doc, catalogue, apply=False):
    if not validate_document(doc):
        raise AcquisitionError("INVALID_DOCUMENT")
    identity = {k: v for k, v in doc.items() if k != "checked_at"}
    document_id = "wsdoc-" + digest(identity)[:48]
    sid = f"ws-{doc['page_id']}"
    source = db.get(Entity, sid)
    genre, author, period = work_policy(doc["title"])
    kind = "HISTORICAL_SOURCE_REPORT" if genre == "PRIMARY_RECORD" else "LITERARY_NARRATIVE"
    source_data = {
        "title": doc["title"],
        "work": doc["title"].split("/")[0],
        "author": author,
        "period": period,
        "url": f"https://zh.wikisource.org/w/index.php?oldid={doc['revision_id']}",
        "edition": f"維基文庫 oldid={doc['revision_id']}; render={doc['html_hash'][:16]}; {PARSER}",
        "kind": genre,
        "provider": "wikisource",
        "upstream_revision": doc["revision_id"],
        "document_id": document_id,
        "document_hash": digest(identity),
        "content_hash": digest(doc["text"]),
        "visibility": "PUBLIC",
        "review_state": "DRAFT",
        "human_review_state": "NOT_REVIEWED",
        "acquisition_state": "PARSED",
        "provenance_state": "EXACT_REVISION_MATCH",
        "rights_state": "ATTRIBUTION_REQUIRED",
        "rights_status": "LICENSED",
        "license": "CC-BY-SA-4.0",
        "license_url": doc["rights"]["url"],
        "rights_evidence_url": doc["rights_evidence_url"],
        "rights_basis": "Ancient original work; Wikisource transcription reused with attribution/share-alike. Modern translations excluded.",
        "attribution": f"《{doc['title']}》；{author}；維基文庫貢獻者；修訂{doc['revision_id']}",
        "changes": "HTML paragraph text extraction; navigation/reference markers removed; no translation. Offsets refer to extracted_text.",
        "access_state": "AVAILABLE",
        "epistemic_kind": kind,
        "independence_group": "work:" + doc["title"].split("/")[0],
    }
    # Do not silently republish a retired/private source on a subsequent discovery.
    if source and (
        source.data.get("visibility") != "PUBLIC"
        or source.data.get("review_state") == "RETIRED"
        or source.data.get("rights_state") == "RESTRICTED"
        or source.data.get("provider") != "wikisource"
    ):
        raise AcquisitionError("SOURCE_ADMIN_RESTRICTED")
    changed = not source or any(source.data.get(k) != v for k, v in source_data.items())
    actions = {
        "source_id": sid,
        "title": doc["title"],
        "revision": doc["revision_id"],
        "changed": changed,
        "quotes": 0,
        "new_claims": 0,
        "updated_links": 0,
        "entities": [],
        "mode": "APPLY" if apply else "DRY_RUN",
    }
    if apply:
        if not db.get(Entity, document_id):
            create(db, "source_document", "source-pipeline", {**identity, "visibility": "PRIVATE"}, document_id)
        if changed:
            if source:
                source = revise(db, source, source.version, source_data, "source-pipeline")
                from .knowledge_api import invalidate_dependents

                invalidate_dependents(db, sid, "source-pipeline")
            else:
                source = create(db, "source", "source-pipeline", source_data, sid)
        # Availability is separately versioned so successful checks do not stale all quotations.
        health_id = sid + "-health"
        health = db.get(Entity, health_id)
        health_data = {"source_id": sid, "checked_at": doc["checked_at"], "status": "AVAILABLE"}
        if health and health.data.get("status") != "AVAILABLE":
            # Offline/cache replay cannot erase a more recent failure/rights observation.
            if datetime.fromisoformat(doc["checked_at"]) <= datetime.fromisoformat(
                health.data.get("last_attempt_at", health.data["checked_at"])
            ):
                health_data = health.data
        if health and health.data != health_data:
            revise(db, health, health.version, health_data, "source-pipeline")
        elif not health:
            create(db, "source_health", "source-pipeline", health_data, health_id)
        # Bibliographic graph, separate from event/ownership claims. A catalogue
        # compiler attribution is not automatically a historical fact assertion.
        work = doc["title"].split("/")[0]
        work_id = "work-" + digest(work)[:32]
        if not db.get(Entity, work_id):
            create(
                db,
                "knowledge_entity",
                "source-pipeline",
                {
                    "name": work,
                    "entity_type": "Work",
                    "aliases": [],
                    "epistemic_kind": kind,
                    "human_review_state": "NOT_REVIEWED",
                    "machine_validation": "AUTOMATED_ATTRIBUTION",
                    "visibility": "PUBLIC",
                },
                work_id,
            )
        edge = "bib-" + digest([sid, work_id])[:40]
        if not db.get(Entity, edge):
            create(
                db,
                "evidence_edge",
                "source-pipeline",
                {
                    "from_id": sid,
                    "to_id": work_id,
                    "relation": "EDITION_OF",
                    "verification": "PROVIDER_TITLE",
                    "visibility": "PUBLIC",
                },
                edge,
            )
        for author_part in re.split("[；、]", author):
            name = re.sub(r"（.*?）|等.*|編.*|；.*", "", author_part).removeprefix("含").removesuffix("注")
            if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or name in ("佚名", "傳本作者"):
                continue
            person_id = "person-" + digest(name)[:32]
            if not db.get(Entity, person_id):
                create(
                    db,
                    "knowledge_entity",
                    "source-pipeline",
                    {
                        "name": name,
                        "entity_type": "Person",
                        "aliases": [],
                        "human_review_state": "NOT_REVIEWED",
                        "machine_validation": "AUTOMATED_ATTRIBUTION",
                        "visibility": "PUBLIC",
                    },
                    person_id,
                )
            edge = "bib-" + digest([work_id, person_id])[:40]
            if not db.get(Entity, edge):
                create(
                    db,
                    "evidence_edge",
                    "source-pipeline",
                    {
                        "from_id": work_id,
                        "to_id": person_id,
                        "relation": "ATTRIBUTED_AUTHOR_OR_COMPILER",
                        "verification": "BIBLIOGRAPHIC_POLICY_METADATA",
                        "source_id": sid,
                        "human_review_state": "NOT_REVIEWED",
                        "visibility": "PUBLIC",
                    },
                    edge,
                )
    version = source.version if source else 1
    for part in doc["paragraphs"]:
        if len(part["text"]) > 5000:
            continue  # Long unsegmented pages require a better parser, no arbitrary slicing.
        linked = [(e, link_alias(e, part["text"], doc["title"])) for e in catalogue]
        linked = [(e, a) for e, a in linked if a]
        if not linked:
            continue
        pid = "wsp-" + digest([document_id, part["locator"], part["offset"]])[:48]
        pdata = {
            "source_id": sid,
            "content": part["text"],
            "text_hash": digest(part["text"]),
            "locator": part["locator"],
            "document_offset": part["offset"],
            "visibility": "PUBLIC",
        }
        if apply and not db.get(Entity, pid):
            create(db, "passage", "source-pipeline", pdata, pid)
        for entity, alias in linked:
            cid = "wsc-" + digest([pid, entity["id"], version])[:48]
            actions["quotes"] += 1
            actions["entities"].append(entity["id"])
            existing = db.get(Entity, cid)
            if existing:
                if (
                    existing.data.get("presentation_track") == "AUTO_VERIFIED_SOURCE"
                    and existing.data.get("review_state") == "DRAFT"
                    and existing.data.get("entity_alias") != alias
                ):
                    actions["updated_links"] += 1
                    if apply:
                        revise(
                            db, existing, existing.version, {**existing.data, "entity_alias": alias}, "source-pipeline"
                        )
                        from .api import _invalidate_claim

                        _invalidate_claim(db, existing.id, "source-pipeline")
                continue
            actions["new_claims"] += 1
            if apply:
                create(
                    db,
                    "claim",
                    "source-pipeline",
                    {
                        "source_id": sid,
                        "source_version": version,
                        "passage_id": pid,
                        "passage_version": 1,
                        "horse_id": entity["id"],
                        "subject_entity_ids": [entity["id"]],
                        "span": [0, len(part["text"])],
                        "text": f"《{doc['title']}》段落提及{entity['name']}；实体归属为自动候选，未验证事件蕴含。",
                        "entity_alias": alias,
                        "relation": "MENTIONS",
                        "proposition_key": "",
                        "epistemic_status": "ATTESTED" if genre == "PRIMARY_RECORD" else "LITERARY",
                        "epistemic_kind": kind,
                        "review_state": "DRAFT",
                        "human_review_state": "NOT_REVIEWED",
                        "machine_validation": "VERIFIED_QUOTATION",
                        "presentation_track": "AUTO_VERIFIED_SOURCE",
                        "entailment": "UNVERIFIED",
                        "visibility": "PUBLIC",
                    },
                    cid,
                )
                edge_id = "wse-" + digest([cid, entity["id"]])[:48]
                create(
                    db,
                    "evidence_edge",
                    "source-pipeline",
                    {
                        "from_id": pid,
                        "to_id": entity["id"],
                        "claim_id": cid,
                        "relation": "MENTIONS",
                        "link_method": "EXACT_ALIAS_CANDIDATE",
                        "identity_verified": False,
                        "visibility": "PUBLIC",
                    },
                    edge_id,
                )
    actions["entities"] = sorted(set(actions["entities"]))
    return actions
