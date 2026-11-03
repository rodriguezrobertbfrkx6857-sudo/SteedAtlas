"""Actual original chat -> candidate -> exact revision -> local agent, no fake approved data."""

import json
import secrets
import time
import urllib.request

from paths import ROOT
from playwright.sync_api import sync_playwright

WEB = "http://127.0.0.1:5175"
API = "http://127.0.0.1:8003"
shots = ROOT / "reports/screenshots/rag-upgrade"
shots.mkdir(parents=True, exist_ok=True)


def api(path, data):
    req = urllib.request.Request(
        API + path, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


phone = "138" + str(time.time_ns())[-8:]
password = secrets.token_urlsafe(18)
api("/api/v1/auth/register", {"phone": phone, "password": password, "nickname": "rag-local-qa"})
login = api("/api/v1/auth/login", {"phone": phone, "password": password})
token = login.get("access_token") or login.get("accessToken")
result = {"scope": "ISOLATED_DATABASE_COPY", "steps": [], "errors": []}
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.on("pageerror", lambda e: result["errors"].append(str(e)))
    page.goto(WEB + "/chat", wait_until="networkidle")
    page.evaluate(
        '(t)=>localStorage.setItem("auth-storage",JSON.stringify({state:{accessToken:t,isAuthenticated:true},accessToken:t,isAuthenticated:true}))',
        token,
    )
    page.reload(wait_until="networkidle")
    # Use the original chat composer where available, then inspect the scoped evidence panel.
    inputs = page.locator('input[placeholder^="输入你想了解"]')
    assert inputs.count() == 1
    inputs.first.fill("赤兔的史籍出处是什么？")
    with page.expect_response(lambda r: "/api/v1/chat" in r.url and r.request.method == "POST") as chat_response:
        inputs.first.press("Enter")
    assert chat_response.value.status == 200
    result["steps"].append("original_chat_submit")
    panel = page.locator("#steedatlas-evidence")
    panel.get_by_text("待核候选：", exact=False).first.wait_for(timeout=30000)
    panel.scroll_into_view_if_needed()
    page.screenshot(path=str(shots / "chat-evidence-desktop.png"))
    result["answer_mode"] = panel.inner_text() if False else panel.locator("#evidence-content").inner_text()
    with page.expect_popup() as popup:
        panel.get_by_text("待核候选：", exact=False).first.click()
    source = popup.value
    source.wait_for_load_state()
    assert "STALE" in source.locator("body").inner_text()
    assert source.locator("mark").inner_text()
    result["exact_excerpt"] = source.locator("mark").inner_text()
    result["source_url"] = source.url
    source.screenshot(path=str(shots / "exact-citation.png"))
    source.close()
    result["steps"].append("pending_exact_revision_opened")
    panel.get_by_role("textbox", name="证据查询").fill("赤兔和的卢的来源比较")
    panel.get_by_role("button", name="研究与来源比较").click()
    panel.get_by_text("研究提案已保存", exact=False).wait_for(timeout=30000)
    result["trace"] = panel.locator("pre").inner_text()
    assert "search_evidence → OK" in result["trace"]
    page.screenshot(path=str(shots / "research-tools.png"))
    result["steps"].append("real_rule_based_tools")
    page.set_viewport_size({"width": 390, "height": 844})
    panel.scroll_into_view_if_needed()
    page.screenshot(path=str(shots / "chat-evidence-mobile.png"))
    result["mobile_overflow"] = page.evaluate("document.documentElement.scrollWidth>innerWidth")
    assert not result["mobile_overflow"]
    browser.close()
(ROOT / "reports/rag-upgrade/ui-flow.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(result, ensure_ascii=False, indent=2))
assert not result["errors"]
