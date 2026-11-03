"""Browser QA for the original video factory UI running against the V2 backend.

Drives the untouched original dark-gold workflow-studio page in a real browser:
logs in, fills the original content-input node, runs the workflow, waits for the
CPU render, and captures screenshots for visual comparison.
"""

import argparse
import json
import os
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "reports/screenshots"
WEB = os.environ.get("WEB_BASE", "http://127.0.0.1:5173")
API = os.environ.get("API_BASE", "http://127.0.0.1:8002")


def log(message: str) -> None:
    print(f"[browser-qa-v2] {message}", flush=True)


def api(method, path, body=None, token=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read() or b"{}")


def main() -> int:
    global WEB, API, SHOTS
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", default=WEB)
    parser.add_argument("--api", default=API)
    parser.add_argument("--report", default="reports/original-video-factory-v2.json")
    parser.add_argument("--shots", default="reports/screenshots")
    parser.add_argument("--video", default="deliverables/rag-acceptance.mp4")
    args = parser.parse_args()
    WEB, API, SHOTS = args.web, args.api, ROOT / args.shots
    report_path = (ROOT / args.report).resolve()
    video_path = (ROOT / args.video).resolve()
    if (
        not report_path.is_relative_to(ROOT)
        or not SHOTS.resolve().is_relative_to(ROOT)
        or not video_path.is_relative_to(ROOT)
    ):
        raise SystemExit("Project-owned output paths required")
    SHOTS.mkdir(parents=True, exist_ok=True)
    phone = "1370000" + str(int(time.time()) % 10000)
    api("POST", "/api/v1/auth/register", {"phone": phone, "password": "Test123456", "nickname": "browser-qa"})
    login = api("POST", "/api/v1/auth/login", {"phone": phone, "password": "Test123456"})
    token = login.get("access_token") or login.get("accessToken")
    log(f"registered + logged in {phone}")

    result = {"mode": "ORIGINAL_VIDEO_FACTORY_V2", "console_errors": [], "steps": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.on("pageerror", lambda error: result["console_errors"].append(str(error)))
        page.goto(WEB + "/workflow-studio/", wait_until="networkidle")
        page.screenshot(path=str(SHOTS / "vf-01-landing.png"), full_page=False)
        result["steps"].append("landing")

        # The original page reads auth from the shared `auth-storage` localStorage key.
        page.evaluate(
            """(auth) => {
              localStorage.setItem('auth-storage', JSON.stringify(auth));
            }""",
            {
                "state": {"accessToken": token, "access_token": token, "isAuthenticated": True},
                "accessToken": token,
                "access_token": token,
                "isAuthenticated": True,
            },
        )
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(2500)
        page.screenshot(path=str(SHOTS / "vf-02-logged-in.png"))
        result["steps"].append("logged-in")

        # Fill the original content-input node's quick topic textarea.
        topic = "赤兔马为什么成为忠义象征"
        field = page.locator('[data-node-field="topic"]').first
        field.wait_for(state="visible", timeout=15000)
        field.click()
        field.fill(topic)
        field.dispatch_event("input")
        field.dispatch_event("change")
        page.wait_for_timeout(800)
        page.screenshot(path=str(SHOTS / "vf-03-topic-filled.png"))
        result["steps"].append("topic-filled")

        # Keep the run short: 3 shots x 4s.
        for node_id, key, value in (("storyboard", "shotCount", "3"), ("storyboard", "shotSeconds", "4")):
            page.evaluate(
                """([nodeId, fieldKey, fieldValue]) => {
                  const event = new Event('change', {bubbles: true});
                  const select = document.querySelector(`[data-node-id="${nodeId}"] [data-field="${fieldKey}"]`);
                  if (select) { select.value = fieldValue; select.dispatchEvent(event); }
                }""",
                [node_id, key, value],
            )
        page.wait_for_timeout(400)

        page.locator("#runBtn").click()
        page.wait_for_timeout(3000)
        page.screenshot(path=str(SHOTS / "vf-04-running.png"))
        result["steps"].append("running")

        deadline = time.time() + 360
        final_status = ""
        while time.time() < deadline:
            final_status = page.locator("#workflowStatus").inner_text().strip()
            if "完成" in final_status or "失败" in final_status or "取消" in final_status:
                break
            page.wait_for_timeout(3000)
        page.wait_for_timeout(2500)
        page.screenshot(path=str(SHOTS / "vf-05-completed.png"))
        result["steps"].append("completed")
        result["workflow_status"] = final_status

        log_text = page.locator("#runLog").inner_text()
        result["run_log_tail"] = log_text[-1200:]

        has_video = page.locator("#previewVideo").get_attribute("src") or ""
        result["preview_video_src"] = has_video.split("?")[0]
        if has_video:
            result["preview_video_state"] = page.evaluate(
                """async (src) => {
                  const v = document.querySelector('#previewVideo');
                  if (!v) return 'no-element';
                  if (!v.src) return 'no-src';
                  try {
                    const r = await fetch(src, {credentials: 'include'});
                    return r.status + ' ' + (r.headers.get('content-type') || '');
                  } catch (e) { return 'fetch-error: ' + e.message; }
                }""",
                has_video,
            )

        result["download_enabled"] = page.locator("#downloadVideoBtn").is_enabled()
        result["download_label"] = page.locator("#downloadVideoBtn").inner_text().strip()
        result["generated_menu_items"] = page.locator(".video-menu-item").count()
        if has_video:
            media_response = page.request.get(WEB + has_video if has_video.startswith("/") else has_video)
            if media_response.ok:
                video_path.write_bytes(media_response.body())
                result["local_video"] = str(video_path.relative_to(ROOT))
        page.screenshot(path=str(SHOTS / "vf-06-final.png"), full_page=True)
        result["steps"].append("final")

        browser.close()

    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log("workflow_status=" + str(result.get("workflow_status")))
    log("preview_video_state=" + str(result.get("preview_video_state")))
    log("download_enabled=" + str(result.get("download_enabled")))
    log("console_errors=" + str(result["console_errors"][:5]))
    if result["console_errors"]:
        return 1
    if "完成" not in str(result.get("workflow_status")):
        log("workflow did not report completion")
        return 1
    log("BROWSER QA PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
