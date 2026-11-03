"""Bounded evidence research; optional licensed acquisition has no approval tool."""

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException

from .domain import digest
from .knowledge import EvidenceSearch, KnowledgeRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResearchPolicy:
    max_calls: int = 8
    max_seconds: float = 10
    max_evidence: int = 12
    max_rounds: int = 3
    allow_acquisition: bool = False
    max_network_requests: int = 9


class ResearchAgent:
    def __init__(self, db, policy=None, owner=None):
        self.repo = KnowledgeRepository(db)
        self.owner = owner
        self.policy = policy or ResearchPolicy()
        self.trace = []
        self.calls = 0
        self.started = time.monotonic()
        self.discovered = set()
        self.acquired = 0
        self.provider = None

    def call(self, tool, arguments):
        start = time.monotonic()
        try:
            return self._call(tool, arguments)
        except Exception as exc:
            output = {
                "error_type": type(exc).__name__,
                "reason": str(exc.detail) if isinstance(exc, HTTPException) else "TOOL_EXECUTION_FAILED",
            }
            self.trace.append(
                {
                    "tool": tool,
                    "arguments": arguments,
                    "status": "FAILED",
                    "output": output,
                    "output_hash": digest(output),
                    "elapsed_ms": round((time.monotonic() - start) * 1000, 3),
                }
            )
            raise

    def _call(self, tool, arguments):
        allowed = {
            "search_entities",
            "search_evidence",
            "get_passage_revision",
            "compare_sources",
            "inspect_claim_edges",
            "check_coverage",
            "check_project_evidence",
        }
        if self.policy.allow_acquisition:
            allowed.update({"discover_sources", "acquire_source"})
        if tool not in allowed:
            raise HTTPException(403, "TOOL_NOT_ALLOWED")
        if self.calls >= self.policy.max_calls or time.monotonic() - self.started >= self.policy.max_seconds:
            raise HTTPException(429, "RESEARCH_BUDGET_EXHAUSTED")
        self.calls += 1
        start = time.monotonic()
        if tool in ("discover_sources", "acquire_source"):
            if os.environ.get("SOURCE_AUTODISCOVERY_ENABLED") != "1":
                raise HTTPException(409, "SOURCE_ACQUISITION_NOT_ENABLED_ON_THIS_INSTANCE")
            from .source_acquisition import SEEDS, AcquisitionError, WikisourceProvider, ingest_document

            if self.provider is None:
                root = Path(os.environ["STEEDATLAS_ROOT"]).resolve()
                self.provider = WikisourceProvider(
                    root / "runtime/source-cache", self.policy.max_network_requests, timeout=4
                )
            trace_start = len(self.provider.trace)
            try:
                if tool == "discover_sources":
                    entity = next((e for e in self.repo.editorial if e["id"] == arguments.get("entity_id")), None)
                    if not entity:
                        raise HTTPException(422, "KNOWN_CATALOGUE_ENTITY_REQUIRED")
                    candidates = [
                        {"title": t, "permitted_work": True, "provider": "wikisource", "discovery": "TARGET_WORK"}
                        for t in SEEDS.get(entity["id"], [])
                    ]
                    discovery_failure = None
                    try:
                        candidates += self.provider.discover(entity, 2)
                    except AcquisitionError as exc:
                        discovery_failure = str(exc)
                    self.discovered.update(c["title"] for c in candidates if c["permitted_work"])
                    result = {
                        "candidates": candidates,
                        "discovery_failure": discovery_failure,
                        "fallback": "TARGET_WORKS" if discovery_failure and candidates else None,
                    }
                    if discovery_failure and not candidates:
                        result.update(state="BLOCKED", reason=discovery_failure)
                else:
                    title = arguments.get("title")
                    if title not in self.discovered or self.acquired >= 2:
                        raise HTTPException(422, "DISCOVERED_WORK_REQUIRED_OR_PAGE_BUDGET")
                    self.acquired += 1
                    doc = self.provider.fetch(title)
                    catalogue = [
                        {
                            "id": r["id"],
                            "name": r["name"],
                            "aliases": self.repo.rows[r["id"]].data.get("aliases", [])
                            if r["id"] in self.repo.rows
                            else [],
                        }
                        for r in self.repo.editorial
                    ]
                    with self.repo.db.begin_nested():
                        result = ingest_document(self.repo.db, doc, catalogue, apply=True)
                    self.repo.db.commit()
                    self.repo = KnowledgeRepository(self.repo.db)
            except AcquisitionError as exc:
                result = {"state": "BLOCKED", "reason": str(exc), "fallback": "CONTINUE_LOCAL_EVIDENCE"}
                if tool == "acquire_source" and str(exc) not in ("REQUEST_BUDGET", "OFFLINE_CACHE_MISS"):
                    from .source_acquisition import mark_unavailable

                    mark_unavailable(self.repo.db, arguments["title"], str(exc))
                    self.repo = KnowledgeRepository(self.repo.db)
            result["provider_trace"] = self.provider.trace[trace_start:]
        elif tool == "search_entities":
            result = self.repo.entities(arguments["query"])
        elif tool == "search_evidence":
            result = EvidenceSearch(self.repo).search(arguments["query"], "all", self.policy.max_evidence)
        elif tool == "get_passage_revision":
            result = self.repo.revision(arguments["id"], arguments["version"], "passage")
        elif tool == "check_project_evidence":
            from .domain import owned
            from .runtime import claim_guard

            project = owned(self.repo.db, arguments["project_id"], self.owner, "project")
            try:
                claim_guard(self.repo.db, project.data)
                result = {"status": "VALID", "project_version": project.version}
            except ValueError as exc:
                result = {"status": "REVIEW_REQUIRED", "reason": str(exc), "project_version": project.version}
        elif tool == "check_coverage":
            result = self.repo.coverage()
        elif tool == "inspect_claim_edges":
            result = [
                {"claim_id": c.id, "relation": c.data.get("relation"), "proposition_key": c.data.get("proposition_key")}
                for c in self.repo.rows.values()
                if c.kind == "claim" and self.repo.public(c) and c.id in arguments["claim_ids"]
            ]
        else:
            result = [
                {"source_id": s, "independence_group": self.repo.dependency_group(s)}
                for s in arguments["source_ids"]
                if self.repo.public(self.repo.rows.get(s))
            ]
        self.trace.append(
            {
                "tool": tool,
                "arguments": arguments,
                "status": "BLOCKED" if isinstance(result, dict) and result.get("state") == "BLOCKED" else "OK",
                "output": result,
                "output_hash": digest(result),
                "elapsed_ms": round((time.monotonic() - start) * 1000, 3),
            }
        )
        return result

    def run(self, query, strategy="adaptive"):
        """Release an acquisition client on success, budget exit, or exception.

        This instance represents one bounded run. Cleanup failure must not hide
        the original research error or discard an otherwise completed result.
        """
        try:
            return self._run(query, strategy)
        finally:
            provider, self.provider = self.provider, None
            if provider is not None:
                try:
                    provider.close()
                except Exception as exc:
                    # Do not log source text, tokens, or provider credentials.
                    logger.warning("Research provider cleanup failed (%s)", type(exc).__name__)

    def _run(self, query, strategy="adaptive"):
        entities = self.call("search_entities", {"query": query})
        queries = [query]
        if strategy in ("fixed", "adaptive"):
            queries += [e["data"]["name"] for e in entities[: self.policy.max_rounds - 1]]
        evidence = {}
        stop = "PLAN_COMPLETE"
        for q in queries:
            if len(self.trace) >= self.policy.max_calls:
                stop = "CALL_BUDGET"
                break
            if time.monotonic() - self.started >= self.policy.max_seconds:
                stop = "TIME_BUDGET"
                break
            output = self.call("search_evidence", {"query": q})
            evidence.update({h["id"]: h for h in output["results"]})
            if strategy == "adaptive" and evidence and len(entities) <= 1:
                stop = "SIMPLE_EVIDENCE_FOUND"
                break
        acquisition_entities = [e for e in entities if e["data"].get("entity_type", "Horse") == "Horse"]
        if not evidence and acquisition_entities and self.policy.allow_acquisition:
            if (
                len(self.trace) + 3 <= self.policy.max_calls
                and time.monotonic() - self.started < self.policy.max_seconds
            ):
                found = self.call("discover_sources", {"entity_id": acquisition_entities[0]["id"]})
                for candidate in found.get("candidates", []):
                    if not candidate["permitted_work"] or self.acquired >= 2:
                        continue
                    if (
                        len(self.trace) + 2 > self.policy.max_calls
                        or time.monotonic() - self.started >= self.policy.max_seconds
                    ):
                        stop = "ACQUISITION_BUDGET"
                        break
                    self.call("acquire_source", {"title": candidate["title"]})
                    if time.monotonic() - self.started < self.policy.max_seconds:
                        output = self.call("search_evidence", {"query": query})
                        evidence.update({h["id"]: h for h in output["results"]})
                    if evidence:
                        stop = "VERIFIED_EXCERPTS_ACQUIRED"
                        break
        for tool, arguments in [
            ("compare_sources", {"source_ids": sorted({h["citation"]["source_id"] for h in evidence.values()})}),
            ("inspect_claim_edges", {"claim_ids": list(evidence)}),
            ("check_coverage", {}),
        ]:
            if len(self.trace) < self.policy.max_calls and time.monotonic() - self.started < self.policy.max_seconds:
                self.call(tool, arguments)
        return {
            "mode": "RULE_BASED",
            "router": "J0",
            "strategy": strategy,
            "query": query,
            "plan": queries,
            "trace": self.trace,
            "evidence": list(evidence.values())[: self.policy.max_evidence],
            "review_state": "PENDING",
            "proposal_type": "ReviewFinding",
            "stop_reason": stop,
            "findings": [] if evidence else ["NO_VERIFIED_EVIDENCE"],
            "acquired_pages": self.acquired,
            "historical_claim_approval": "NOT_PERFORMED",
            "corpus_snapshot_id": self.repo.snapshot,
            "policy": vars(self.policy),
            "tokens": 0,
            "cost": 0,
            "model": None,
            "jev_status": "BLOCKED_NO_AUTHORIZATION",
        }
