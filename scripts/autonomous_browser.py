"""Real original black/gold UI, source links, culture and agent acceptance on the isolated copy."""

import argparse
import json
import secrets
import sys
import time

import httpx
from paths import ROOT
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
parser = argparse.ArgumentParser()
parser.add_argument("--web", default="http://127.0.0.1:5176")
parser.add_argument("--api", default="http://127.0.0.1:8004")
parser.add_argument("--report", default="reports/rag-upgrade/autonomous/browser.json")
parser.add_argument("--shots", default="reports/screenshots/autonomous")
parser.add_argument("--video", default="runtime/auto-browser-demo.webm")
args = parser.parse_args()
from resume_demo_preflight import owned

WEB, API = args.web, args.api
shots = owned(args.shots)
shots.mkdir(parents=True, exist_ok=True)
result = {"scope": "ISOLATED_DATABASE_COPY", "pages": [], "steps": [], "errors": []}
client = httpx.Client(base_url=API, trust_env=False, timeout=60)
phone, password = "137" + str(time.time_ns())[-8:], secrets.token_urlsafe(18)
registered = client.post(
    "/api/v1/auth/register", json={"phone": phone, "password": password, "nickname": "auto-evidence-demo"}
)
assert registered.status_code == 201, registered.status_code
login = client.post("/api/v1/auth/login", json={"phone": phone, "password": password}).json()
token = login.get("access_token") or login.get("accessToken")
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    context = browser.new_context(
        viewport={"width": 1440, "height": 1000}, record_video_dir=str(ROOT / "runtime/auto-browser-video")
    )
    page = context.new_page()
    page.on("pageerror", lambda e: result["errors"].append(str(e)))
    page.goto(WEB + "/", wait_until="networkidle")
    page.screenshot(path=str(shots / "original-home-baseline.png"))
    for width, height, device in [(1440, 1000, "desktop"), (390, 844, "mobile")]:
        page.set_viewport_size({"width": width, "height": height})
        for route, name in [
            ("/", "home"),
            ("/chat", "chat"),
            ("/atlas", "atlas"),
            ("/workflow-studio/", "factory"),
            ("/gacha", "gacha"),
            ("/collection", "collection"),
            ("/product", "shop"),
            ("/quiz", "quiz"),
        ]:
            response = page.goto(WEB + route, wait_until="networkidle")
            page.screenshot(path=str(shots / f"{name}-{device}.png"))
            result["pages"].append(
                {
                    "route": route,
                    "device": device,
                    "status": response.status,
                    "overflow": page.evaluate("document.documentElement.scrollWidth>innerWidth"),
                }
            )
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(WEB + "/chat", wait_until="networkidle")
    page.evaluate(
        '(t)=>localStorage.setItem("auth-storage",JSON.stringify({state:{accessToken:t,isAuthenticated:true},accessToken:t,isAuthenticated:true}))',
        token,
    )
    page.reload(wait_until="networkidle")
    panel = page.locator("#steedatlas-evidence")
    for name in ("赤兔", "乌骓", "的卢"):
        composer = page.locator('input[placeholder^="输入你想了解"]')
        composer.fill(name + "的史籍出处是什么？")
        with page.expect_response(
            lambda r: "/api/v1/chat" in r.url and r.request.method == "POST", timeout=60000
        ) as response:
            composer.press("Enter")
        assert response.value.status == 200
        payload = response.value.body().decode()
        meta = [json.loads(line[6:]) for line in payload.splitlines() if line.startswith("data: {")]
        meta = next(m for m in meta if m.get("type") == "meta")
        assert meta["review_status"] == "MACHINE_VERIFIED" and meta["citations"]
        panel.locator('a[href^="/api/v2/evidence/"]').first.wait_for(timeout=60000)
        panel.scroll_into_view_if_needed()
        page.screenshot(path=str(shots / f"answer-{name}.png"))
        with page.expect_popup() as popup:
            panel.locator('a[href^="/api/v2/evidence/"]').first.click()
        source = popup.value
        source.wait_for_load_state()
        assert "MACHINE_VERIFIED" in source.locator("body").inner_text()
        assert "STALE" not in source.locator("body").inner_text()
        assert source.locator("mark").inner_text()
        source.screenshot(path=str(shots / f"source-{name}.png"))
        result["steps"].append(
            {
                "name": name,
                "original_chat": True,
                "mode": meta["mode"],
                "verification": meta["review_status"],
                "citations": meta["citations"],
                "opened_exact_quote": source.locator("mark").inner_text(),
            }
        )
        source.close()
    panel.get_by_role("textbox", name="证据查询").fill("赤兔和的卢的史籍来源比较")
    panel.get_by_role("button", name="研究与来源比较").click()
    panel.get_by_text("研究记录已保存", exact=False).wait_for(timeout=60000)
    result["agent_trace"] = panel.locator("pre").inner_text()
    assert "search_evidence → OK" in result["agent_trace"]
    page.screenshot(path=str(shots / "agent-tools-desktop.png"))
    panel.get_by_role("textbox", name="证据查询").fill("我重视责任和守护，哪匹马适合我？")
    panel.get_by_role("button", name="查阅证据").click()
    panel.get_by_text("文化互动／编辑整理", exact=False).wait_for(timeout=60000)
    page.screenshot(path=str(shots / "culture-match.png"))
    page.set_viewport_size({"width": 390, "height": 844})
    panel.scroll_into_view_if_needed()
    page.screenshot(path=str(shots / "culture-mobile.png"))
    result["mobile_flow_overflow"] = page.evaluate("document.documentElement.scrollWidth>innerWidth")
    video = page.video
    context.close()
    output_video = owned(args.video)
    video.save_as(str(output_video))
    result["video"] = str(output_video.relative_to(ROOT))
    browser.close()
client.close()
owned(args.report).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(
    json.dumps(
        {
            "pages": len(result["pages"]),
            "source_flows": len(result["steps"]),
            "errors": result["errors"],
            "video": result["video"],
        },
        ensure_ascii=False,
    )
)
assert not result["errors"] and not result["mobile_flow_overflow"]
assert all(r["status"] == 200 and not r["overflow"] for r in result["pages"])
