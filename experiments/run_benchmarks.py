import copy
import csv
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "wangzhan/{E4A9AA9B-E341-4443-82B1-6CD600640AE6}/files/var/www/baiqipu/server"
sys.path.insert(0, str(SERVER))
from app.services.ai_engine import _cosine_sim, _embed_text
from app.v2.contracts import Project
from app.v2.domain import check_bible, digest, impact, rank, select_roles

out = ROOT / "experiments/results"
out.mkdir(parents=True, exist_ok=True)
dataset_dir = ROOT / "experiments/datasets"
dataset_dir.mkdir(exist_ok=True)
corpus = json.loads((SERVER / "data/corpus.json").read_text(encoding="utf-8-sig"))
docs = [{"id": x["id"], "text": x["text"]} for x in corpus]
queries = [{"query": x["metadata"]["name"], "gold": x["id"], "category": "derived_exact_name"} for x in corpus]
for alias, name in [("赤菟", "赤兔"), ("赤兔马", "赤兔"), ("的颅", "的卢"), ("乌骓马", "乌骓")]:
    doc = next((x for x in corpus if x["metadata"]["name"] == name), None)
    if doc:
        queries.append({"query": alias, "gold": doc["id"], "category": "synthetic_alias"})
dataset = {
    "schema_version": 1,
    "seed": 20261031,
    "provenance": "Derived from legacy corpus, not independent historical adjudication",
    "corpus_sha256": digest(corpus),
    "queries": queries,
}
(dataset_dir / "manifest.json").write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
retrieval = []
for mode in ["B0", "B1"]:
    for q in queries:
        start = time.perf_counter()
        if mode == "B0":
            v = _embed_text(q["query"])
            hits = sorted(
                [{"id": d["id"], "score": _cosine_sim(v, _embed_text(d["text"]))} for d in docs],
                key=lambda d: d["score"],
                reverse=True,
            )
            hits = [h for h in hits if h["score"] > 0]
        else:
            hits = rank(q["query"], docs)
        found = next((i + 1 for i, d in enumerate(hits) if d["id"] == q["gold"]), None)
        retrieval.append(
            {
                "variant": mode,
                "category": q["category"],
                "query": q["query"],
                "recall_at_5": int(found is not None and found <= 5),
                "reciprocal_rank": 1 / found if found else 0,
                "latency_ms": (time.perf_counter() - start) * 1000,
            }
        )


def write_csv(name, rows):
    with (out / name).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


write_csv("retrieval.csv", retrieval)

base = Project.model_validate(
    {
        "title": "offline",
        "scenes": [{"id": f"s{i}", "text": "明确标记的艺术演绎", "duration_ticks": 24} for i in range(3)],
    }
).model_dump()
intents = [
    ("complete_script", "plan", copy.deepcopy(base)),
    ("subtitle", "subtitle", copy.deepcopy(base)),
    ("evidence_gap", "evidence", copy.deepcopy(base)),
    ("repair", "repair", copy.deepcopy(base)),
]
intents[2][2]["scenes"][0]["label"] = "ATTESTED"
intents.append(("empty_script", "plan", copy.deepcopy(base)))
intents[-1][2]["scenes"][0]["text"] = ""
routing = []
for case, intent, p in intents:
    for variant in ["S0", "S1", "S2"]:
        start = time.perf_counter()
        roles = (
            ["PLANNER"]
            if variant == "S0"
            else ["RESEARCH", "NARRATIVE", "DIRECTOR", "REVIEW", "REPAIR"]
            if variant == "S1"
            else select_roles(p, intent)[0]
        )
        routing.append(
            {
                "variant": variant,
                "case": case,
                "selected_role_count": len(roles),
                "roles": "+".join(roles),
                "actual_llm_calls": 0,
                "mode": "OFFLINE_CONTROLLER",
                "latency_ms": (time.perf_counter() - start) * 1000,
            }
        )
write_csv("routing.csv", routing)

recovery = []
for count in [1, 3, 5]:
    before = copy.deepcopy(base)
    before["scenes"] = [{**base["scenes"][0], "id": f"s{i}"} for i in range(count)]
    for case in ["subtitle", "visual", "audio", "bible", "claim_status", "claim_retired", "missing_file"]:
        after = copy.deepcopy(before)
        knowledge = case.startswith("claim")
        if case == "subtitle":
            after["scenes"][0]["text"] = "修改后的字幕"
        if case == "visual":
            after["scenes"][0]["asset_id"] = "new-asset"
        if case == "audio":
            after["audio_asset_ids"] = ["new-audio"]
        if case == "bible":
            after["bible"]["period"] = "新设定"
        decisions = impact(before, after, "claim" if knowledge else "project")
        # R2+ and R3 share the same observable dependency completeness and conservative guard.
        gold = (
            {s["id"] for s in after["scenes"]}
            if knowledge or case in {"audio", "bible", "missing_file"}
            else {after["scenes"][0]["id"]}
        )
        for variant in ["R0", "R1", "R2", "R2+", "R3"]:
            if variant in {"R0", "R1"}:
                invalid = {s["id"] for s in after["scenes"]}
            elif variant == "R2" and knowledge:
                invalid = set()
            elif variant in {"R2+", "R3"}:
                invalid = {k for k, v in decisions.items() if v["decision"] != "REUSE_ALLOWED"}
                if case in {"audio", "missing_file"}:
                    invalid = {s["id"] for s in after["scenes"]}
            else:
                invalid = gold.copy()
            recovery.append(
                {
                    "variant": variant,
                    "case": case,
                    "scene_count": count,
                    "rebuild_or_review_scenes": len(invalid),
                    "unsafe_reuse_count": len(gold - invalid),
                    "affected_opportunities": len(gold),
                    "false_invalidation_count": len(invalid - gold),
                    "cpu_render_seconds": "not_measured_in_policy_simulator",
                    "mode": "SYNTHETIC_POLICY_POC",
                }
            )
write_csv("recovery.csv", recovery)

consistency = []
for name in ["no_bible", "global_only", "structured"]:
    p = copy.deepcopy(base)
    p["bible"]["period"] = "东汉"
    p["scenes"][1]["period"] = "秦末"
    findings = check_bible(p) if name == "structured" else []
    consistency.append(
        {
            "variant": name,
            "injected_metadata_conflicts": 1,
            "detected": len(findings),
            "mode": "DETERMINISTIC_METADATA_ONLY",
        }
    )
write_csv("consistency.csv", consistency)

rng = random.Random(20261031)
metrics = []
for mode in ["B0", "B1"]:
    vals = [x["reciprocal_rank"] for x in retrieval if x["variant"] == mode]
    samples = sorted(sum(rng.choices(vals, k=len(vals))) / len(vals) for _ in range(1000))
    metrics.append(
        {
            "family": "retrieval",
            "variant": mode,
            "n": len(vals),
            "mrr": sum(vals) / len(vals),
            "ci_low": samples[25],
            "ci_high": samples[974],
            "recall_at_5": sum(x["recall_at_5"] for x in retrieval if x["variant"] == mode) / len(vals),
        }
    )
write_csv("metrics.csv", metrics)
(out / "seeds.json").write_text(
    json.dumps({"bootstrap": 20261031, "resamples": 1000, "all_llm_calls": 0}), encoding="utf-8"
)
report = (
    """# 科研 POC 实测

本轮为探索性离线实验；没有真实 LLM、没有人类盲评、没有供应商计费调用。研究目标尚未证明。

## 检索
"""
    + "\n".join(
        f"- {m['variant']}：n={m['n']}，MRR={m['mrr']:.4f}，query bootstrap 95% CI=[{m['ci_low']:.4f},{m['ci_high']:.4f}]，Recall@5={m['recall_at_5']:.4f}"
        for m in metrics
    )
    + """

gold 来自原记录的精确名称，不是独立标注，也没有未见实体划分；不代表史实准确率、泛化或用户问答能力。别名四题为合成烟测；未报告未支持事实率或人工评审一致性。

## 自适应调度
5 个合成任务分别实际执行控制器。S0/S1 是固定角色选择策略，S2 使用真实 select_roles；LLM 调用数均为 0。角色数减少只能说明规则跳过生效，不能推出模型质量、成本或人工返工改善。

## 增量恢复
1/3/5 场景 × 7 类合成编辑，5 策略；R2+ 包含完整可见知识版本/状态和保守失效。R2+ 与 R3 在本 POC 上一致，未测到 R3 的额外收益。R2 的知识状态遗漏作为负面对照，不当作强基线。
这些是策略调用数，不是 CPU 出片耗时。实际媒体耗时与文件验证另见 deliverables/demo-manifest.json。音频变更采用保守全场景失效；尚未实现词级语音对齐。

## Scene Bible
三个控制条件只检查一个注入的年代元数据矛盾。结构化规则能发现该矛盾，不代表真实视频画面一致性。
"""
)
(ROOT / "reports/RESEARCH_FINDINGS.md").write_text(report, encoding="utf-8")
(out / "ablations.md").write_text(
    "本轮已运行：B0/B1、S0/S1/S2 角色控制、R0/R1/R2/R2+/R3 策略、Scene Bible 元数据规则。未运行：真实 LLM 生成、人类盲评、Dense/Hybrid、词级语音/多模态一致性。",
    encoding="utf-8",
)
print(report)
