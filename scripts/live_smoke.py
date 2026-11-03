"""Live-stack smoke test: register a user, log in, and drive the V2 compat workflow
through the Vite dev server proxy (exactly the path the browser uses)."""

import json
import os
import time
import urllib.error
import urllib.request

WEB = os.environ.get("WEB_BASE", "http://127.0.0.1:5173")
BASE = WEB + "/api/v2/compat/workflow"


def log(message: str) -> None:
    print(f"[live-smoke] {message}", flush=True)


def call(method, url, body=None, token=None, raw=False):
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
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
            return exc.code, {"raw": payload[:400].decode("utf-8", "replace")}, dict(exc.headers)


def main() -> int:
    phone = "1390000" + str(int(time.time()) % 10000)
    payload = {"phone": phone, "password": "Test123456", "nickname": "live-smoke"}
    status, body, _ = call("POST", WEB + "/api/v1/auth/register", payload)
    if status not in (200, 201):
        log(f"register failed ({status}): {body}")
        return 1
    log(f"registered {phone}")

    status, body, _ = call("POST", WEB + "/api/v1/auth/login", {"phone": phone, "password": "Test123456"})
    if status != 200:
        log(f"login failed ({status}): {body}")
        return 1
    token = body.get("access_token") or body.get("accessToken")
    log("login ok")

    status, body, _ = call("GET", BASE + "/provider-status", token=token)
    if status != 200:
        log(f"provider-status failed ({status}): {body}")
        return 1
    log(f"provider-status ok mode={body.get('mode')} veo.external={body.get('veo', {}).get('external')}")

    status, body, _ = call(
        "POST",
        BASE + "/tasks",
        token=token,
        body={
            "title": "乌骓：项羽帐下的那匹马",
            "horse_name": "乌骓",
            "duration": 18,
            "aspect_ratio": "9:16",
            "workflow_definition": {"name": "baiqipu-video-factory-site-workflow", "nodes": [], "connections": []},
            "input_payload": {
                "topic": "乌骓：项羽帐下的那匹马",
                "horse": "乌骓",
                "horse_name": "乌骓",
                "brief": "区分史料与传说",
                "aspect_ratio": "9:16",
                "storyboard": {"shotCount": "3", "shotSeconds": "6"},
            },
            "auto_start": True,
        },
    )
    if status != 200:
        log(f"create task failed ({status}): {body}")
        return 1
    task_id = body["task"]["task_id"]
    log(f"task created {task_id}")

    deadline = time.time() + 300
    final = None
    while time.time() < deadline:
        status, final, _ = call("GET", BASE + f"/tasks/{task_id}", token=token)
        if status != 200:
            log(f"poll failed ({status}): {final}")
            return 1
        if final["status"] not in {"queued", "processing"}:
            break
        time.sleep(2.0)
    if not final or final["status"] != "completed":
        log(f"task did not complete: {json.dumps(final, ensure_ascii=False)[:1200]}")
        return 1
    log("task completed")

    video_url = final["result_payload"].get("videoUrl")
    log("videoUrl=" + str(video_url))

    status, payload, headers = call("GET", BASE + f"/tasks/{task_id}/download", token=token, raw=True)
    if status != 200 or len(payload) < 5000:
        log(f"download failed ({status}) bytes={len(payload)}")
        return 1
    log(f"download ok {len(payload)} bytes")

    status, payload, _ = call("GET", WEB + video_url, raw=True)
    if status != 200 or len(payload) < 5000:
        log(f"media ticket failed ({status})")
        return 1
    log(f"signed media ok {len(payload)} bytes")

    status, body, _ = call("GET", BASE + "/tasks?limit=5", token=token)
    if status != 200 or not body.get("items"):
        log("task list failed")
        return 1
    log(f"task list ok ({len(body['items'])} items)")

    status, _, _ = call("DELETE", BASE + f"/tasks/{task_id}", token=token)
    if status != 200:
        log(f"delete failed ({status})")
        return 1
    log("delete ok")

    log("LIVE SMOKE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
