"""Real CPU render of a machine-verified quotation through the existing V2 DAG."""

import argparse
import hashlib
import json
import secrets
import sys
import time

import httpx
from paths import ROOT

sys.stdout.reconfigure(encoding="utf-8")
parser = argparse.ArgumentParser()
parser.add_argument("--api", default="http://127.0.0.1:8004")
parser.add_argument("--report", default="reports/rag-upgrade/autonomous/source-video.json")
parser.add_argument("--video", default="deliverables/autonomous-source-quote.mp4")
args = parser.parse_args()
from resume_demo_preflight import owned

client = httpx.Client(base_url=args.api, trust_env=False, timeout=60)


def call(method, path, data=None):
    r = client.request(method, path, json=data)
    r.raise_for_status()
    return r.json()


phone, password = "136" + str(time.time_ns())[-8:], secrets.token_urlsafe(18)
call("POST", "/api/v1/auth/register", {"phone": phone, "password": password, "nickname": "source-video-qa"})
login = call("POST", "/api/v1/auth/login", {"phone": phone, "password": password})
client.headers["Authorization"] = "Bearer " + (login.get("access_token") or login["accessToken"])
answer = call(
    "POST", "/api/v2/answers", {"messages": [{"role": "user", "content": "赤兔的史书出处"}], "scope": "history"}
)
citation = next(c for c in answer["citations"] if c["source_title"] == "三國志/卷07")
quote = "布有良馬曰赤兔。"
assert quote in citation["quote"]
project = call(
    "POST",
    "/api/v2/projects",
    {
        "title": "赤兔原文 · 机器核对引文演示",
        "horse_id": "chitu",
        "scenes": [
            {
                "id": "quote",
                "text": quote,
                "duration_ticks": 96,
                "label": "SOURCE_ATTRIBUTED",
                "claim_refs": [citation["claim_id"] + "@" + str(citation["claim_revision"])],
            }
        ],
    },
)
approved = call(
    "POST",
    "/api/v2/projects/" + project["id"] + "/approve",
    {"expected_version": project["version"], "idempotency_key": "local-quote-project-approval"},
)
job = call(
    "POST",
    "/api/v2/projects/" + project["id"] + "/renders",
    {"expected_version": approved["version"], "idempotency_key": "local-quote-render"},
)
deadline = time.monotonic() + 150
while time.monotonic() < deadline:
    state = call("GET", "/api/v2/jobs/" + job["id"])
    if state["status"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
        break
    time.sleep(2)
assert state["status"] == "SUCCEEDED", state["status"]
node = next(n for n in state["nodes"] if n["kind"] == "compose")
video = client.get(node["download"])
video.raise_for_status()
path = owned(args.video)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_bytes(video.content)
result = {
    "status": state["status"],
    "job_id": job["id"],
    "project_id": project["id"],
    "source_citation": citation,
    "scene_label": "SOURCE_ATTRIBUTED",
    "video": str(path.relative_to(ROOT)),
    "video_bytes": len(video.content),
    "sha256": hashlib.sha256(video.content).hexdigest(),
    "nodes": [{k: n.get(k) for k in ("key", "kind", "state", "output")} for n in state["nodes"]],
    "historical_claim_review": "NOT_PERFORMED",
    "project_approval": "LOCAL_RENDER_REQUEST_ONLY",
    "paid_api_calls": 0,
}
owned(args.report).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(
    json.dumps(
        {"status": result["status"], "video": result["video"], "bytes": result["video_bytes"]}, ensure_ascii=False
    )
)
