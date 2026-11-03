"""A0-A12 acceptance evidence collector.

Runs the real acceptance probes against the live stack and writes a machine
readable evidence file. Nothing here fabricates a result: every probe records
its actual command output, HTTP status, or file hash.
"""

import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = os.environ.get("WEB_BASE", "http://127.0.0.1:5173")
API = os.environ.get("API_BASE", "http://127.0.0.1:8002")
EVIDENCE = ROOT / "reports/acceptance-evidence.json"


def log(message: str) -> None:
    print(f"[acceptance] {message}", flush=True)


def call(method, url, body=None, token=None, raw=False, accept="application/json"):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": accept}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = response.read()
            if raw:
                return response.status, payload, dict(response.headers)
            return response.status, json.loads(payload or b"{}"), dict(response.headers)
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        if raw:
            return exc.code, payload, dict(exc.headers)
        try:
            return exc.code, json.loads(payload or b"{}"), dict(exc.headers)
        except json.JSONDecodeError:
            return exc.code, {"raw": payload[:300].decode("utf-8", "replace")}, dict(exc.headers)


def run(command, cwd=ROOT, timeout=900):
    try:
        proc = subprocess.run(command, cwd=str(cwd), capture_output=True, timeout=timeout)
    except FileNotFoundError as exc:
        return {
            "command": " ".join(str(x) for x in command),
            "returncode": 127,
            "stdout_tail": "",
            "stderr_tail": f"executable not found: {exc}",
        }
    return {
        "command": " ".join(str(x) for x in command),
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout.decode("utf-8", "replace")[-3000:],
        "stderr_tail": proc.stderr.decode("utf-8", "replace")[-2000:],
    }


def main() -> int:
    evidence = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "probes": {}}

    evidence["probes"]["A0_git"] = {
        "status": run(["git", "status", "--short"]),
        "branch": run(["git", "branch", "--show-current"]),
        "log": run(["git", "log", "-6", "--oneline"]),
    }

    phone = "1360000" + str(int(time.time()) % 10000)
    call("POST", API + "/api/v1/auth/register", {"phone": phone, "password": "Test123456", "nickname": "acceptance"})
    login = call("POST", API + "/api/v1/auth/login", {"phone": phone, "password": "Test123456"})[1]
    token = login.get("access_token") or login.get("accessToken")

    probes = {}
    probes["ai_build_unauth_401"] = call("POST", API + "/api/v1/ai/build", body={"docs": []})[0]
    probes["legacy_video_write_frozen_409"] = call(
        "POST", API + "/api/v1/video/workflow/tasks", {"title": "x"}, token=token
    )[0]
    probes["generated_private_requires_auth"] = call("GET", API + "/generated/secret.mp4")[0]
    probes["v2_project_unauth_401"] = call("GET", API + "/api/v2/projects")[0]
    probes["compat_tasks_unauth_401"] = call("GET", API + "/api/v2/compat/workflow/tasks")[0]
    probes["capabilities"] = call("GET", API + "/api/v2/capabilities")[1]
    evidence["probes"]["A1_security"] = probes

    status, sources, _ = call("GET", API + "/api/v2/sources", token=token)
    evidence["probes"]["A4_sources"] = {
        "status": status,
        "count": len(sources) if isinstance(sources, list) else 0,
        "sample_review_states": sorted(
            {str(item.get("data", {}).get("review_state")) for item in sources[:50]}
        )
        if isinstance(sources, list)
        else [],
    }
    status, search, _ = call("GET", API + "/api/v2/search?q=%E8%B5%A4%E5%85%94&mode=history", token=token)
    evidence["probes"]["A4_search"] = {
        "status": status,
        "mode": search.get("mode"),
        "results": len(search.get("results", [])),
    }

    project_body = {
        "title": "验收：赤兔马三幕演示",
        "horse_id": "chitu",
        "scenes": [
            {"id": f"s{i}", "text": f"第{i}幕：循着记载，认识名马。", "duration_ticks": 48} for i in range(1, 4)
        ],
        "width": 1280,
        "height": 720,
        "fps_num": 24,
    }
    status, project, _ = call("POST", API + "/api/v2/projects", project_body, token=token)
    project_id = project["id"]
    approved = call(
        "POST",
        API + f"/api/v2/projects/{project_id}/approve",
        {"expected_version": project["version"], "idempotency_key": "acceptance-approval"},
        token=token,
    )[1]
    render = call(
        "POST",
        API + f"/api/v2/projects/{project_id}/renders",
        {"expected_version": approved["version"], "idempotency_key": "acceptance-render"},
        token=token,
    )
    evidence["probes"]["A5_render_enqueued"] = {"status": render[0], "body": render[1]}

    job_id = render[1].get("id")
    deadline = time.time() + 300
    job_state = {}
    while time.time() < deadline:
        job_state = call("GET", API + f"/api/v2/jobs/{job_id}", token=token)[1]
        if job_state.get("status") not in {"READY", "RUNNING"}:
            break
        time.sleep(2.0)
    evidence["probes"]["A7_job_state"] = job_state

    reloaded = call("GET", API + f"/api/v2/projects/{project_id}", token=token)[1]
    evidence["probes"]["A5_persistence"] = {
        "project_id": reloaded.get("id"),
        "version": reloaded.get("version"),
        "scene_count": len(reloaded.get("data", {}).get("scenes", [])),
        "timeline_clips": len(reloaded.get("timeline", {}).get("tracks", [{}])[0].get("clips", [])),
    }

    compose_node = next((n for n in job_state.get("nodes", []) if n["kind"] == "compose"), None)
    if compose_node and compose_node.get("download"):
        status, payload, headers = call("GET", API + compose_node["download"], token=token, raw=True)
        if status == 200:
            mp4 = ROOT / "deliverables/acceptance-render.mp4"
            mp4.parent.mkdir(parents=True, exist_ok=True)
            mp4.write_bytes(payload)
            probe = run(
                ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(mp4)]
            )
            evidence["probes"]["A6_ffprobe"] = {
                "returncode": probe["returncode"],
                "stdout": probe["stdout_tail"][:4000],
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
                "path": str(mp4),
            }

    subtitle_node = next((n for n in job_state.get("nodes", []) if n["kind"] == "subtitle"), None)
    if subtitle_node and subtitle_node.get("download"):
        status, payload, _ = call("GET", API + subtitle_node["download"], token=token, raw=True)
        if status == 200:
            srt_path = ROOT / "deliverables/acceptance-render.srt"
            srt_path.write_bytes(payload)
            evidence["probes"]["A6_srt"] = {
                "status": status,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "head": payload.decode("utf-8", "replace")[:400],
                "path": str(srt_path),
            }

    evidence["probes"]["A6_environment"] = {
        "ffmpeg_binary": run(["ffmpeg", "-version"])["stdout_tail"].splitlines()[:1],
        "gpu_device_count": 0 if run(["nvidia-smi", "-L"])["returncode"] != 0 else None,
        "gpu_present": run(["nvidia-smi", "-L"])["returncode"] == 0,
        "openai_key_configured": bool(os.environ.get("OPENAI_API_KEY")),
        "video_factory_api_mode": os.environ.get("VIDEO_FACTORY_API_MODE", "unset"),
        "renderer": "FFmpeg CPU (no GPU, no local video model)",
    }

    status, agent_catalogue, _ = call("GET", API + "/api/v2/agent-providers", token=token)
    live_attempt = call(
        "POST",
        API + f"/api/v2/projects/{project_id}/agent-runs",
        {"intent": "plan", "mode": "LIVE_LLM", "expected_version": reloaded["version"], "max_turns": 2},
        token=token,
    )
    rule_attempt = call(
        "POST",
        API + f"/api/v2/projects/{project_id}/agent-runs",
        {"intent": "plan", "mode": "RULE_BASED", "expected_version": reloaded["version"], "max_turns": 2},
        token=token,
    )
    evidence["probes"]["A8_agent"] = {
        "catalogue_status": status,
        "catalogue": agent_catalogue,
        "live_llm_status": live_attempt[0],
        "live_llm_detail": live_attempt[1],
        "rule_based_status": rule_attempt[0],
        "rule_based_traces": call(
            "GET", API + f"/api/v2/projects/{project_id}/agent-runs", token=token
        )[1],
    }

    lineage = call("GET", API + f"/api/v2/projects/{project_id}/lineage", token=token)[1]
    evidence["probes"]["A9_lineage"] = {
        "edges": len(lineage.get("edges", [])),
        "relations": sorted({edge.get("relation") for edge in lineage.get("edges", [])}),
        "unknown_semantic_dependencies": lineage.get("unknown_semantic_dependencies"),
    }

    evidence["probes"]["A10_licences"] = {
        "THIRD_PARTY_NOTICES": (ROOT / "THIRD_PARTY_NOTICES.md").exists(),
        "frontend_sbom": (ROOT / "docs/frontend-sbom.json").exists(),
        "dependency_inventory": (ROOT / "docs/dependency-inventory.json").exists(),
    }

    evidence["probes"]["UI0_home"] = {"status": call("GET", WEB + "/", accept="text/html", raw=True)[0]}
    evidence["probes"]["UI0_workflow_studio"] = {
        "status": call("GET", WEB + "/workflow-studio/", accept="text/html", raw=True)[0]
    }

    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"evidence written to {EVIDENCE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
