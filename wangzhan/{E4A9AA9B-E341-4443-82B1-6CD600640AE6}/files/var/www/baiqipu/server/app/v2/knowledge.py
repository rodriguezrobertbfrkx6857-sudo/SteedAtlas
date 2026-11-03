"""One read model for evidence. Rebuilt from transaction state; no stale vector cache.

Scores mean lexical relevance, never historical confidence. Editorial profiles and
creative prompts are separate collections and cannot become supporting citations.
"""

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import select

from .domain import ALIASES, digest, pack, rank
from .models import Entity, Revision
from .source_acquisition import normalized

KNOWLEDGE_KINDS = (
    "source",
    "passage",
    "claim",
    "knowledge_entity",
    "evidence_edge",
    "source_health",
    "source_document",
)


def normalize(text):
    text = normalized(text)
    value = (
        unicodedata.normalize("NFKC", text)
        .lower()
        .translate(
            str.maketrans("呂馬盧烏騅關劉備漢傳騎顱項義書記國時詩說", "吕马卢乌骓关刘备汉传骑颅项义书记国时诗说")
        )
    )
    for alias, canonical in ALIASES.items():
        value = value.replace(alias, canonical)
    return value


class KnowledgeRepository:
    def __init__(self, db, snapshot_only=False):
        self.snapshot_only = snapshot_only
        self.db = db
        self.document_checks = {}
        self.rows = {e.id: e for e in db.scalars(select(Entity).where(Entity.kind.in_(KNOWLEDGE_KINDS)))}
        # Preserve the original catalogue shape; it remains explicitly editorial.
        from app.routers.horses import _build_rag_library_items

        self.editorial = _build_rag_library_items(db)
        corpus_file = Path(__file__).resolve().parents[2] / "data/corpus.json"
        self.legacy_editorial = json.loads(corpus_file.read_text(encoding="utf-8-sig")) if corpus_file.exists() else []
        self.snapshot = digest(
            {
                "entities": sorted((e.id, e.version, digest(e.data)) for e in self.rows.values()),
                "editorial": self.editorial,
                "legacy_editorial": self.legacy_editorial,
            }
        )

    def public(self, e):
        if not e or e.data.get("visibility", "PUBLIC") != "PUBLIC":
            return False
        if e.kind in ("claim", "passage"):
            s = self.rows.get(e.data.get("source_id"))
            if not (
                s
                and s.kind == "source"
                and s.data.get("visibility", "PUBLIC") == "PUBLIC"
                and s.data.get("rights_status") in ("PUBLIC_DOMAIN", "LICENSED")
                and s.data.get("rights_state") not in ("UNKNOWN", "RESTRICTED")
            ):
                return False
            health = self.rows.get(s.id + "-health")
            if health and health.data.get("status") == "UNAVAILABLE":
                return False
            if e.kind == "claim":
                p = self.rows.get(e.data.get("passage_id"))
                return bool(p and p.kind == "passage" and self.public(p))
            return True
        return True

    def revision(self, identity, version, kind=None):
        e = self.rows.get(identity)
        if not self.public(e) or (kind and e.kind != kind):
            raise HTTPException(404, "Evidence not found")
        r = self.db.scalar(select(Revision).where(Revision.entity_id == identity, Revision.version == version))
        if not r:
            raise HTTPException(404, "Evidence revision not found")
        return r.data

    def entities(self, query):
        q = normalize(query)
        result = []
        for e in self.rows.values():
            if e.kind == "knowledge_entity" and self.public(e):
                if any(
                    normalize(n) in q and (len(n) >= 2 or normalize(n) == q)
                    for n in [e.data.get("name", ""), *e.data.get("aliases", []), e.id]
                    if n
                ):
                    result.append(pack(e))
        for row in self.editorial:
            if any(normalize(n) in q for n in [row["id"], row["name"]] if n) and not any(
                e["id"] == row["id"] for e in result
            ):
                result.append(
                    {
                        "id": row["id"],
                        "kind": "knowledge_entity",
                        "version": 1,
                        "data": {"name": row["name"], "entity_type": "Horse", "aliases": []},
                    }
                )
        return result

    def subjects(self, claim):
        values = set(claim.data.get("subject_entity_ids", []))
        if claim.data.get("horse_id"):
            values.add(claim.data["horse_id"])
        # Legacy name-only claims are readable, migration persists unambiguous IDs.
        if not values and claim.data.get("horse_name"):
            values.update(e["id"] for e in self.entities(claim.data["horse_name"]))
        return values

    def dependency_group(self, source_id):
        seen = set()

        def walk(identity):
            if identity in seen:
                return []
            seen.add(identity)
            s = self.rows.get(identity)
            if not s or s.kind != "source":
                return ["UNKNOWN"]
            if s.data.get("independence_group"):
                return [s.data["independence_group"]]
            parents = s.data.get("derived_from", [])
            return [x for p in parents for x in walk(p)] if parents else ["UNKNOWN"]

        return sorted(set(walk(source_id))) or ["UNKNOWN"]

    def citation(self, claim, require_approved=True):
        d = claim.data
        s, p = self.rows.get(d.get("source_id")), self.rows.get(d.get("passage_id"))
        if not self.public(claim) or not self.public(p) or not s or not p or s.kind != "source" or p.kind != "passage":
            return None
        if p.data.get("source_id") != s.id or p.version != d.get("passage_version"):
            return None
        if d.get("source_version") != s.version:
            return None
        if any(x.data.get("review_state") == "RETIRED" for x in (s, p, claim)):
            return None
        machine = d.get("presentation_track") == "AUTO_VERIFIED_SOURCE"
        if machine:
            from .evidence_policy import machine_quotation

            if not machine_quotation(self, claim, s, p):
                return None
        elif require_approved and d.get("review_state") != "APPROVED":
            return None
        if s.data.get("rights_status") not in ("PUBLIC_DOMAIN", "LICENSED"):
            return None
        if not s.data.get("edition") or not s.data.get("url", "").startswith("https://") or not p.data.get("locator"):
            return None
        content = p.data.get("content", "")
        span = d.get("span") or [0, len(content)]
        if len(span) != 2 or not all(isinstance(x, int) for x in span) or not 0 <= span[0] < span[1] <= len(content):
            return None
        if p.data.get("text_hash") != digest(content):
            return None
        genre = s.data.get("kind", "EDITORIAL")
        if d.get("epistemic_status") == "ATTESTED" and genre not in ("PRIMARY_RECORD", "SCHOLARLY"):
            return None
        return {
            "claim_id": claim.id,
            "claim_revision": claim.version,
            "source_id": s.id,
            "source_revision": s.version,
            "passage_id": p.id,
            "passage_revision": p.version,
            "span": span,
            "quote": content[span[0] : span[1]],
            "locator": p.data.get("locator", ""),
            "source_title": s.data.get("title", ""),
            "edition": s.data.get("edition", ""),
            "source_url": s.data.get("url", ""),
            "genre": genre,
            "relation": d.get("relation"),
            "epistemic_status": d.get("epistemic_status"),
            "review_state": d.get("review_state"),
            "verification": ("MACHINE_VERIFIED_SNAPSHOT" if self.snapshot_only else "MACHINE_VERIFIED")
            if machine
            else "CURATED_EXCERPT",
            "source_observation": (self.rows.get(s.id + "-health").data if self.rows.get(s.id + "-health") else {}),
            "snapshot_only": self.snapshot_only,
            "human_review_state": d.get("human_review_state", "LEGACY_REVIEW_STATE"),
            "presentation_track": d.get("presentation_track", "CURATED"),
            "epistemic_kind": d.get("epistemic_kind", d.get("epistemic_status")),
            "entailment": d.get("entailment", "CURATED"),
            "entity_identity": "ALIAS_CANDIDATE_NOT_IDENTITY_PROOF" if machine else "CURATED",
            "attribution": s.data.get("attribution", ""),
            "license": s.data.get("license", s.data.get("rights_status")),
            "license_url": s.data.get("license_url", ""),
            "changes": s.data.get("changes", ""),
            "upstream_revision": s.data.get("upstream_revision"),
            "independence_group": self.dependency_group(s.id),
            "proposition_key": d.get("proposition_key", ""),
            "href": f"/api/v2/evidence/{quote(claim.id, safe='')}@{claim.version}",
            "index_snapshot_id": self.snapshot,
        }

    def validate(self, citation):
        c = self.rows.get(citation.get("claim_id"))
        current = self.citation(c) if c and c.kind == "claim" else None
        keys = (
            "claim_revision",
            "source_id",
            "source_revision",
            "passage_id",
            "passage_revision",
            "span",
            "quote",
            "genre",
            "relation",
            "review_state",
            "verification",
            "source_url",
            "edition",
            "locator",
            "human_review_state",
            "license",
        )
        return bool(current and all(current[k] == citation.get(k) for k in keys))

    def coverage(self):
        claims = [e for e in self.rows.values() if e.kind == "claim" and self.public(e)]
        return {
            "corpus_snapshot_id": self.snapshot,
            "editorial_count": len(self.editorial),
            "legacy_editorial_count": len(self.legacy_editorial),
            "claim_count": len(claims),
            "review_states": dict(Counter(e.data.get("review_state", "DRAFT") for e in claims)),
            "citable_count": sum(bool(self.citation(e)) for e in claims),
            "machine_verified_count": sum(
                bool(self.citation(e)) and e.data.get("presentation_track") == "AUTO_VERIFIED_SOURCE" for e in claims
            ),
            "human_reviewed_count": sum(e.data.get("human_review_state") == "REVIEWED" for e in claims),
            "llm_available": False,
            "source_present": any(e.kind == "source" and self.public(e) for e in self.rows.values()),
            "index_ready": True,
            "evidence_verified": any(self.citation(e) for e in claims),
        }

    def browse_editorial(self, query, limit=5):
        docs = [
            {
                "id": "editorial:" + str(d["id"]),
                "text": d.get("text", ""),
                "knowledge_class": "EDITORIAL",
                "review_state": "UNVERIFIED",
                "usable_as_fact": False,
                "revision": digest(d),
            }
            for d in self.legacy_editorial
        ]
        return rank(normalize(query), [{**d, "text": normalize(d["text"])} for d in docs])[:limit]

    def creative_search(self, query, limit=5):
        path = Path(__file__).resolve().parents[2] / "data/video_factory_rag.json"
        docs = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else []
        rows = [
            {
                "id": d["id"],
                "text": normalize(d.get("text", "")),
                "knowledge_class": "CREATIVE",
                "usable_as_fact": False,
                "revision": digest(d),
            }
            for d in docs
        ]
        return {
            "creative_snapshot_id": digest(docs),
            "count": len(rows),
            "results": rank(normalize(query), rows)[:limit],
        }

    def candidates(self, query, limit=8, scope="all"):
        ids = {e["id"] for e in self.entities(query)}
        docs = []
        for c in self.rows.values():
            if c.kind != "claim" or not self.public(c) or c.data.get("review_state") == "RETIRED":
                continue
            p = self.rows.get(c.data.get("passage_id"))
            s = self.rows.get(c.data.get("source_id"))
            if not p or p.kind != "passage" or not s or s.data.get("review_state") == "RETIRED":
                continue
            if not self.public(p) or (
                c.data.get("presentation_track") == "AUTO_VERIFIED_SOURCE" and not self.citation(c)
            ):
                continue
            if ids and not self.subjects(c).intersection(ids):
                continue
            docs.append(
                {
                    "id": c.id,
                    "version": c.version,
                    "text": normalize(p.data.get("content", "") + " " + c.data.get("text", "")),
                    "source_title": s.data.get("title", ""),
                    "genre": s.data.get("kind", "EDITORIAL"),
                    "review_state": c.data.get("review_state", "DRAFT"),
                    "locator": p.data.get("locator", ""),
                    "href": f"/api/v2/evidence/{c.id}@{c.version}",
                    "usable_as_fact": bool(self.citation(c))
                    and c.data.get("presentation_track") != "AUTO_VERIFIED_SOURCE",
                    "usable_as_attributed_quote": bool(self.citation(c)),
                    "verification": "MACHINE_VERIFIED"
                    if self.citation(c) and c.data.get("presentation_track") == "AUTO_VERIFIED_SOURCE"
                    else c.data.get("review_state", "DRAFT"),
                }
            )
        linked = {c.data.get("passage_id") for c in self.rows.values() if c.kind == "claim"}
        for p in self.rows.values():
            if p.kind != "passage" or p.id in linked or not self.public(p) or p.data.get("review_state") == "RETIRED":
                continue
            s = self.rows.get(p.data["source_id"])
            if s.data.get("review_state") == "RETIRED":
                continue
            docs.append(
                {
                    "id": p.id,
                    "version": p.version,
                    "text": normalize(p.data["content"]),
                    "source_title": s.data.get("title", ""),
                    "genre": s.data.get("kind", "EDITORIAL"),
                    "review_state": "UNREVIEWED_PASSAGE",
                    "locator": p.data.get("locator", ""),
                    "href": f"/api/v2/passage-evidence/{p.id}@{p.version}",
                    "usable_as_fact": False,
                }
            )
        genres = {"history": {"PRIMARY_RECORD", "SCHOLARLY"}, "literature": {"LITERARY_WORK"}}
        docs = [d for d in docs if scope == "all" or d["genre"] in genres.get(scope, set())]
        return rank(normalize(query), docs)[:limit]


class EvidenceSearch:
    def __init__(self, repository):
        self.repo = repository

    def search(self, query, scope="history", limit=8):
        limit = max(1, min(int(limit), 50))
        entities = self.repo.entities(query)
        ids = {e["id"] for e in entities if e["data"].get("entity_type", "Horse") == "Horse"}
        works = {e["data"]["name"] for e in entities if e["data"].get("entity_type") == "Work"}
        docs = []
        for c in self.repo.rows.values():
            if c.kind != "claim":
                continue
            citation = self.repo.citation(c)
            if not citation or (scope == "history" and citation["epistemic_status"] != "ATTESTED"):
                continue
            if scope == "literature" and citation["genre"] != "LITERARY_WORK":
                continue
            if citation["epistemic_status"] in ("CREATIVE", "EDITORIAL"):
                continue
            subjects = self.repo.subjects(c)
            if ids and not ids.intersection(subjects):
                continue
            if works and self.repo.rows[citation["source_id"]].data.get("work") not in works:
                continue
            p = self.repo.rows[citation["passage_id"]]
            names = " ".join(e["data"]["name"] for e in entities if e["id"] in subjects)
            docs.append(
                {
                    "id": c.id,
                    "version": c.version,
                    "text": normalize(names + " " + p.data["content"] + " " + c.data["text"]),
                    "claim": c.data,
                    "citation": citation,
                }
            )
        ranked = rank(normalize(query), docs)
        hits = []

        def add(hit):
            if len(hits) < limit and not any(h["id"] == hit["id"] for h in hits):
                hits.append(hit)

        # Compare only explicit reviewed propositions on the same entity. A shared
        # word, unknown proposition, or machine MENTIONS never implies conflict.
        def opposes(a, b):
            x, y = a["citation"], b["citation"]
            return bool(
                x["proposition_key"]
                and x["proposition_key"] == y["proposition_key"]
                and {x["relation"], y["relation"]} == {"SUPPORTS", "CONTRADICTS"}
                and x["genre"] in ("PRIMARY_RECORD", "SCHOLARLY")
                and y["genre"] in ("PRIMARY_RECORD", "SCHOLARLY")
                and self.repo.subjects(self.repo.rows[a["id"]]) & self.repo.subjects(self.repo.rows[b["id"]])
            )

        oppositions = []
        for h in ranked:
            for d in docs:
                if opposes(h, d):
                    oppositions.append((h, {**d, "score": 0, "ranking_reason": "EXPLICIT_OPPOSITION"}))
        # Reserve pairs before ordinary source diversity. Hard limit applies to
        # every stage; uncovered entities/opposition are reported explicitly.
        for a, b in oppositions:
            add(a)
            add(b)
        for identity in sorted(ids):
            hit = next((h for h in ranked if identity in self.repo.subjects(self.repo.rows[h["id"]])), None)
            if hit:
                add(hit)
        for h in ranked:
            if h["citation"]["source_id"] not in {x["citation"]["source_id"] for x in hits}:
                add(h)
        for h in ranked:
            add(h)
        selected = {h["id"] for h in hits}
        covered = set().union(*(self.repo.subjects(self.repo.rows[h["id"]]) for h in hits)) if hits else set()
        coverage = {
            "limit": limit,
            "missing_entity_ids": sorted(ids - covered),
            "known_opposition_pairs": len({tuple(sorted((a["id"], b["id"]))) for a, b in oppositions}),
            "opposition_truncated": any(a["id"] not in selected or b["id"] not in selected for a, b in oppositions),
            "conflict_detection": "EXPLICIT_PROPOSITION_SAME_ENTITY_ONLY",
        }
        components = []
        for h in hits:
            group = set(h["citation"]["independence_group"])
            if h["citation"]["relation"] != "SUPPORTS" or "UNKNOWN" in group:
                continue
            overlap = [part for part in components if part & group]
            components = [part for part in components if not part & group]
            components.append(group.union(*overlap))
        return {
            "corpus_snapshot_id": self.repo.snapshot,
            "results": hits,
            "entities": entities,
            "candidates": self.repo.candidates(query, limit, scope),
            "coverage": coverage,
            "editorial": self.repo.browse_editorial(query, limit),
            "independent_support_groups": len(components),
            "score_semantics": "LEXICAL_RELEVANCE_ONLY",
            "scope": scope,
            "mode": "RETRIEVAL_ONLY" if hits else "INSUFFICIENT_EVIDENCE",
        }


class AnswerService:
    def __init__(self, db, user=None):
        self.repo = KnowledgeRepository(db)
        self.user = user

    def answer(self, messages, scope="all"):
        user = [m["content"][:2000] for m in messages[-12:] if m.get("role") == "user"]
        query = user[-1] if user else ""
        from .culture import culture_reply

        culture = culture_reply(self.repo.db, query, self.user)
        if culture:
            return {**self.envelope("CULTURE", culture["message"], [], [], query), **culture}
        explicit = self.repo.entities(query)
        context = []
        if not explicit and re.search("它|这匹|那匹|前者|后者|其主人|出处|原文|接着|继续", query):
            for old in reversed(user[:-1]):
                context = [e for e in self.repo.entities(old) if e["data"].get("entity_type", "Horse") == "Horse"]
                if context:
                    break
            if len(context) != 1 and (context or re.search("它|这匹|那匹|前者|后者|其主人", query)):
                return self.envelope("CLARIFY", "请说明要追问哪匹马或哪位人物。", [], [], query)
            if context:
                query = context[0]["data"]["name"] + " " + query
        if scope == "all":
            historical = bool(re.search("史书|史籍|史料|史实|正史", query))
            literary = bool(re.search("小说|文学|演义|演義", query))
            if historical and not literary:
                scope = "history"
            elif literary and not historical:
                scope = "literature"
        bundle = EvidenceSearch(self.repo).search(query, scope, limit=4)
        citations = [h["citation"] for h in bundle["results"] if self.repo.validate(h["citation"])]
        supports = [h for h in bundle["results"] if h["citation"]["relation"] == "SUPPORTS"]
        conflict = []
        for a in citations:
            for b in citations:
                if (
                    a["proposition_key"]
                    and a["proposition_key"] == b["proposition_key"]
                    and self.repo.subjects(self.repo.rows[a["claim_id"]])
                    & self.repo.subjects(self.repo.rows[b["claim_id"]])
                    and a["genre"] in ("PRIMARY_RECORD", "SCHOLARLY")
                    and b["genre"] in ("PRIMARY_RECORD", "SCHOLARLY")
                    and {a["relation"], b["relation"]} == {"SUPPORTS", "CONTRADICTS"}
                ):
                    conflict.append(a["proposition_key"])
        if citations:
            machine = any(c["verification"] == "MACHINE_VERIFIED" for c in citations)
            if machine:
                mode = (
                    "SOURCE_CONFLICT"
                    if conflict
                    else "LITERARY_ATTRIBUTED"
                    if all(c["genre"] == "LITERARY_WORK" for c in citations)
                    else "SOURCE_ATTRIBUTED"
                )
                names = (
                    "、".join(
                        e["data"]["name"]
                        for e in bundle["entities"]
                        if e["data"].get("entity_type", "Horse") == "Horse"
                    )
                    or "本次查询"
                )
                works = "、".join(dict.fromkeys(c["source_title"] for c in citations))
                summary = f"找到《{works}》对{names}的明确提及；这能确认所引版本中出现相关文字，同名仍不等于同一实体。"
                unsupported = bool(
                    re.search("出生|生于|哪年|哪月|哪日|具体日期|唯一主人|最后结局|最终结局", normalize(query))
                )
                if unsupported:
                    mode = "INSUFFICIENT"
                    summary = "不能据现有提及记录确定所问的日期、唯一归属或最终结局；本次没有经过语义核验的对应关系。以下仅供核对原文。"
                if bundle["coverage"]["missing_entity_ids"] or bundle["coverage"]["opposition_truncated"]:
                    summary += "检索展示预算不足以覆盖全部实体或已知反证，请缩小比较范围；不能据此宣称没有反证。"
                heading = (
                    summary
                    + "\n\n机器已核对下列版本、原文和引用位置；未经过人工或专家审核。引文仅说明文献如何记载，不证明事件真实，也未验证它能支持问题中的全部主张。"
                )
                if any(c["genre"] == "LITERARY_WORK" for c in citations):
                    heading += "文学叙事另行标注，不能直接作为史实。"
                if conflict:
                    heading += "同一主张存在来源分歧，当前不能定论。"
                text = (
                    heading
                    + "\n\n"
                    + "\n\n".join(
                        f"[{i}] 【{'文学叙事' if c['genre'] == 'LITERARY_WORK' else '文献记载'}】《{c['source_title']}》{c['locator']}：\n“{c['quote']}”\n{c['attribution']} · {c['license']}"
                        for i, c in enumerate(citations[:4], 1)
                    )
                )
                return self.envelope(mode, text, citations[:4], [], query, bundle)
            mode = (
                "CONFLICT"
                if conflict
                else "INTERPRETIVE"
                if any(c["genre"] == "LITERARY_WORK" for c in citations)
                else "SYNTHESIS"
                if supports
                else "INSUFFICIENT"
            )
            heading = {
                "CONFLICT": "同一主张存在已审证据分歧，请对照来源，不能据此定论。",
                "INTERPRETIVE": "以下区分文献记载与文学叙事；文学描写不能直接证明史实。",
                "SYNTHESIS": "以下仅摘录已审核的文献归属式陈述，不代表模型推理。",
                "INSUFFICIENT": "现有片段仅提及或反对该主张，不足以支持结论。",
            }[mode]
            atomic = [
                {
                    "text": f"《{h['citation']['source_title']}》记载：“{h['citation']['quote']}”",
                    "evidence": [h["citation"]],
                    "relation": h["citation"]["relation"],
                }
                for h in supports
            ]
            text = (
                heading
                + "\n\n"
                + "\n\n".join(
                    f"[{i}] 《{c['source_title']}》{c['locator']}：“{c['quote']}”（{c['relation']}）"
                    for i, c in enumerate(citations, 1)
                )
            )
            return self.envelope(mode, text, citations, atomic, query, bundle)
        snapshot_bundle = EvidenceSearch(KnowledgeRepository(self.repo.db, snapshot_only=True)).search(query, scope, 4)
        bundle["snapshots"] = [
            {
                "title": h["citation"]["source_title"],
                "href": "/api/v2/snapshot-evidence/" + h["id"],
                "observation": h["citation"]["source_observation"],
                "status": "ARCHIVED_NOT_CURRENT",
            }
            for h in snapshot_bundle["results"]
            if h["citation"]["verification"] == "MACHINE_VERIFIED_SNAPSHOT"
        ]
        ids = {e["id"] for e in bundle["entities"]}
        editorial = [r for r in self.repo.editorial if r["id"] in ids]
        # Questions seeking proof must not be answered with an editorial story.
        proof = any(
            x in query
            for x in (
                "史实",
                "证据",
                "出处",
                "真实",
                "是否",
                "证明",
                "矛盾",
                "史籍",
                "史书",
                "原文",
                "文献",
                "记载",
                "引文",
            )
        )
        if editorial and not proof:
            text = "编辑资料浏览（未核验，不能作为历史事实引文）：\n\n" + "\n\n".join(
                r["name"] + "：" + r["story"][:600] for r in editorial[:3]
            )
            return self.envelope("BROWSE", text, [], [], query, bundle)
        return self.envelope(
            "INSUFFICIENT",
            "本库尚无足够的可核验精确证据回答该问题；这不表示历史上不存在相关记载。",
            [],
            [],
            query,
            bundle,
        )

    def envelope(self, mode, text, citations, atomic, query, bundle=None):
        return {
            "mode": mode,
            "message": text,
            "summary": text.split("\n\n", 1)[0],
            "citations": citations,
            "atomic_claims": atomic,
            "evidence": bundle or {},
            "resolved_query": query,
            "generation_mode": "RETRIEVAL_ONLY",
            "model": None,
            "tokens": 0,
            "cost": 0,
            "review_status": "MACHINE_VERIFIED"
            if any(c.get("verification") == "MACHINE_VERIFIED" for c in citations)
            else "REVIEWED_EXCERPTS"
            if citations
            else "UNVERIFIED",
            "corpus_snapshot_id": self.repo.snapshot,
            "provenance_digest": digest(citations),
            "sources": [
                {
                    "title": c["source_title"],
                    "source": c["source_title"],
                    "snippet": c["quote"],
                    "horse_name": "",
                    "url": c["href"],
                    **c,
                }
                for c in citations
            ],
            "matched_horse": None,
            "recommended_product": None,
            "personality_match": None,
            "recommendation_strategy": None,
        }


def bind_claim(db, data):
    repo = KnowledgeRepository(db)
    s, p = repo.rows.get(data["source_id"]), repo.rows.get(data["passage_id"])
    if (
        not s
        or s.kind != "source"
        or not p
        or p.kind != "passage"
        or p.data["source_id"] != s.id
        or p.version != data["passage_version"]
    ):
        raise HTTPException(422, "INVALID_PASSAGE_REFERENCE")
    data = {
        **data,
        "source_version": data.get("source_version") or s.version,
        "span": data.get("span") or [0, len(p.data["content"])],
    }
    if data["source_version"] != s.version or not 0 <= data["span"][0] < data["span"][1] <= len(p.data["content"]):
        raise HTTPException(422, "INVALID_EVIDENCE_VERSION_OR_SPAN")
    ids = set(data.get("subject_entity_ids", []))
    if data.get("horse_id"):
        ids.add(data["horse_id"])
    known = {r["id"] for r in repo.editorial} | {e.id for e in repo.rows.values() if e.kind == "knowledge_entity"}
    if not ids <= known:
        raise HTTPException(422, "UNKNOWN_SUBJECT_ENTITY")
    return {**data, "subject_entity_ids": sorted(ids)}


def record_answer(db, user, result):
    """Private immutable answer audit; no generated-answer cache is served."""
    if user is None:
        return result
    from .domain import create

    e = create(db, "knowledge_answer", user.id, result)
    db.commit()
    return {**result, "answer_id": e.id}
