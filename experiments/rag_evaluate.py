"""Reproducible diagnostic comparison and unlabelled real-corpus QA traces. No paid calls."""

import json
import math
import os
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "wangzhan/{E4A9AA9B-E341-4443-82B1-6CD600640AE6}/files/var/www/baiqipu/server"
database = (ROOT / (ROOT / "runtime/rag-demo-path.txt").read_text(encoding="utf-8")).resolve()
assert database.is_relative_to(ROOT)
os.environ.update(
    DATABASE_URL="sqlite:///" + database.as_posix(),
    DEBUG="false",
    SECRET_KEY="offline-eval-" + "x" * 48,
    STEEDATLAS_ROOT=str(ROOT),
)
sys.path.insert(0, str(SERVER))
from app.database import SessionLocal
from app.services.ai_engine import _cosine_sim, _embed_text
from app.v2.domain import digest, rank
from app.v2.knowledge import AnswerService, normalize
from app.v2.research import ResearchAgent, ResearchPolicy

out = ROOT / "reports/rag-upgrade"
out.mkdir(parents=True, exist_ok=True)
corpus = json.loads((SERVER / "data/corpus.json").read_text(encoding="utf-8-sig"))
docs = [{"id": d["id"], "text": d["text"]} for d in corpus]
queries = [{"query": d["metadata"]["name"], "target": d["id"], "category": "derived_name"} for d in corpus]
for alias, name in [("赤菟", "赤兔"), ("赤兔马", "赤兔"), ("的颅", "的卢"), ("乌骓马", "乌骓")]:
    queries.append(
        {
            "query": alias,
            "target": next(d["id"] for d in corpus if d["metadata"]["name"] == name),
            "category": "synthetic_alias",
        }
    )
bags = {d["id"]: _embed_text(d["text"]) for d in docs}
raw = []
for q in queries:
    v = _embed_text(q["query"])
    for variant in ["V1_COUNTER", "R0_NORMALIZED_BM25", "SPARSE_RRF"]:
        start = time.perf_counter()
        old = sorted(
            [{"id": d["id"], "score": _cosine_sim(v, bags[d["id"]])} for d in docs],
            key=lambda d: d["score"],
            reverse=True,
        )
        old = [d for d in old if d["score"] > 0]
        if variant == "V1_COUNTER":
            hits = old
        else:
            bm = rank(normalize(q["query"]), [{**d, "text": normalize(d["text"])} for d in docs])
            if variant == "R0_NORMALIZED_BM25":
                hits = bm
            else:
                scores = {}
                for ranking in [old, bm]:
                    for i, d in enumerate(ranking):
                        scores[d["id"]] = scores.get(d["id"], 0) + 1 / (60 + i + 1)
                hits = [{"id": k} for k in sorted(scores, key=scores.get, reverse=True)]
        found = next((i + 1 for i, d in enumerate(hits) if d["id"] == q["target"]), None)
        raw.append(
            {
                **q,
                "variant": variant,
                "rank": found,
                "recall_at_5": int(bool(found and found <= 5)),
                "rr": 1 / found if found else 0,
                "ndcg_at_5": 1 / math.log2(found + 1) if found and found <= 5 else 0,
                "latency_ms": (time.perf_counter() - start) * 1000,
            }
        )


def quantile(xs, p):
    return sorted(xs)[min(len(xs) - 1, int((len(xs) - 1) * p))]


def bootstrap(xs):
    rng = random.Random(20261101)
    values = sorted(statistics.mean(rng.choices(xs, k=len(xs))) for _ in range(1000))
    return [values[24], values[974]]


metrics = []
for variant in sorted({r["variant"] for r in raw}):
    rs = [r for r in raw if r["variant"] == variant]
    metrics.append(
        {
            "variant": variant,
            "n": len(rs),
            "mrr": statistics.mean(r["rr"] for r in rs),
            "mrr_bootstrap_95_ci": bootstrap([r["rr"] for r in rs]),
            "recall_at_5": statistics.mean(r["recall_at_5"] for r in rs),
            "ndcg_at_5": statistics.mean(r["ndcg_at_5"] for r in rs),
            "p50_ms": quantile([r["latency_ms"] for r in rs], 0.5),
            "p95_ms": quantile([r["latency_ms"] for r in rs], 0.95),
        }
    )
complex_queries = json.loads((ROOT / "experiments/datasets/rag-upgrade/questions.json").read_text(encoding="utf-8"))
answers = []
agents = []
with SessionLocal() as db:
    service = AnswerService(db)
    coverage = service.repo.coverage()
    for q in complex_queries:
        start = time.perf_counter()
        a = service.answer([{"role": "user", "content": q["question"]}])
        answers.append(
            {
                "id": q["id"],
                "category": q["category"],
                "query": q["question"],
                "mode": a["mode"],
                "citation_count": len(a["citations"]),
                "valid_spans": sum(service.repo.validate(c) for c in a["citations"]),
                "latency_ms": (time.perf_counter() - start) * 1000,
                "gold": None,
            }
        )
    for strategy in ["single", "fixed", "adaptive"]:
        result = ResearchAgent(db, ResearchPolicy(max_calls=8)).run("赤兔与的卢的出处比较", strategy)
        agents.append(result)
    # A positive trace must read actual revisions even when no evidence has been human approved.
    agent = ResearchAgent(db)
    candidates = agent.call("search_evidence", {"query": "赤兔"})
    if candidates["candidates"]:
        c = service.repo.rows[candidates["candidates"][0]["id"]]
        agent.call("get_passage_revision", {"id": c.data["passage_id"], "version": c.data["passage_version"]})
    trace = agent.trace
report = {
    "dataset_kind": "NAME_DIAGNOSTIC_NOT_HISTORICAL_GOLD",
    "corpus_sha256": digest(corpus),
    "metrics": metrics,
    "complex_n": len(answers),
    "coverage": coverage,
    "gold_count": 0,
    "human_annotators": 0,
    "complex_quality_metrics": "BLOCKED_NO_GOLD",
    "dense_hybrid": "NOT_RUN_NO_GO_PENDING_GOLD",
    "tokens": 0,
    "paid_cost": 0,
    "agent_quality_gain": "NOT_ESTABLISHED; inspect actual search-call counts",
}
for filename, value in [
    ("evaluation.json", report),
    ("retrieval-raw.json", raw),
    ("answers-raw.json", answers),
    ("agent-comparison.json", agents),
    ("agent-real-trace.json", trace),
]:
    (out / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
