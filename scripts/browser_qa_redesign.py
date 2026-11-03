import json
import uuid
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / "reports/screenshots"
out.mkdir(parents=True, exist_ok=True)
result = {"mode": "REAL_BROWSER_LOCAL_CPU", "checks": [], "console_errors": []}
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
    page.on("pageerror", lambda e: result["console_errors"].append(str(e)))
    page.goto("http://127.0.0.1:5173/", wait_until="networkidle")
    page.locator("h1").wait_for()
    page.screenshot(path=str(out / "home-desktop.png"), full_page=True)
    result["checks"].append("home renders")
    page.get_by_role("link", name="名马图鉴", exact=True).click()
    page.get_by_role("textbox", name="搜索名马").fill("赤兔")
    page.locator(".catalogue-card").first.click()
    page.get_by_role("heading", name="赤兔", exact=True).wait_for()
    page.get_by_role("button", name="打开精确引文").first.click()
    page.get_by_role("dialog", name="精确引用").wait_for()
    page.screenshot(path=str(out / "passage.png"))
    page.get_by_role("button", name="关闭 ×", exact=True).click()
    result["checks"].append("catalogue to exact passage")
    page.get_by_role("button", name="以这匹马开始创作").click()
    identity = "local-qa-" + uuid.uuid4().hex[:10]
    page.get_by_role("textbox", name="账号", exact=True).fill(identity)
    page.get_by_label("密码", exact=True).fill(uuid.uuid4().hex)
    page.get_by_role("button", name="注册新账号").click()
    page.get_by_role("dialog").wait_for(state="hidden")
    page.get_by_role("button", name="以这匹马开始创作").click()
    page.get_by_role("textbox", name="工程标题").wait_for()
    page.get_by_role("textbox", name="工程标题").fill("浏览器端到端真实出片")
    page.get_by_role("button", name="保存修订", exact=True).click()
    page.get_by_text("已保存 · 修订", exact=False).wait_for()
    page.reload(wait_until="networkidle")
    page.screenshot(path=str(out/"after-reload.png"),full_page=True)
    page.get_by_role("button", name="浏览器端到端真实出片", exact=False).first.click()
    assert page.get_by_role("textbox", name="工程标题").input_value() == "浏览器端到端真实出片"
    result["checks"].append("project survives reload")
    page.get_by_role("button", name="检查分镜并提出建议").click()
    page.get_by_text("DIRECTOR → REVIEW", exact=True).wait_for()
    page.get_by_role("button", name="专家视图", exact=True).click()
    page.get_by_role("button", name="编译与校验依赖").click()
    page.get_by_role("table").wait_for()
    page.screenshot(path=str(out / "studio-desktop.png"), full_page=True)
    page.get_by_role("button", name="我已审阅此版本").click()
    page.get_by_role("button", name="导出真实 MP4").click()
    page.get_by_role("heading", name="导出任务 · SUCCEEDED").wait_for(timeout=120000)
    page.get_by_role("button", name="预览视频", exact=True).click()
    page.locator("video").wait_for()
    page.screenshot(path=str(out / "export.png"), full_page=True)
    result["checks"].append("register create edit save proposal compile approve render preview")
    page.goto("http://127.0.0.1:5173/#home", wait_until="networkidle")
    page.set_viewport_size({"width": 320, "height": 800})
    page.screenshot(path=str(out / "home-mobile.png"), full_page=True)
    overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth")
    assert not overflow, "320px horizontal overflow"
    result["checks"].append("320px no horizontal overflow")
    page.goto("http://127.0.0.1:5173/#studio", wait_until="networkidle")
    if page.get_by_role("textbox", name="工程标题").count() == 0:
        page.get_by_role("button", name="浏览器端到端真实出片", exact=False).first.click()
    page.screenshot(path=str(out / "studio-mobile.png"), full_page=True)
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), "320px studio overflow"
    result["checks"].append("320px studio no horizontal overflow")
    result["browser"] = browser.version
    result["performance"] = page.evaluate(
        '({navigation:performance.getEntriesByType("navigation")[0]?.toJSON(),paint:performance.getEntriesByType("paint").map(p=>p.toJSON())})'
    )
    browser.close()
(ROOT / "reports/browser-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=True))
