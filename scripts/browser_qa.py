"""Verify the original UI remains the default; redesign tests are separate."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser=p.chromium.launch(channel="msedge",headless=True)
    page=browser.new_page(viewport={"width":1440,"height":1000})
    errors=[]
    page.on("pageerror",lambda error:errors.append(str(error)))
    page.goto("http://127.0.0.1:5173/",wait_until="networkidle")
    assert "AI驱动的历史名马数字化商业系统" in page.title()
    assert page.locator("script[src*=index-CpqDpQs9]").count()==1
    assert page.locator("link[href*=index-CAKZiFLw]").count()==1
    assert page.get_by_text("让历史奔跑在心间",exact=True).count()>0
    page.screenshot(path=str(ROOT/"reports/screenshots/original-restored.png"))
    assert not errors,errors
    (ROOT/"reports/original-ui-browser.json").write_text(json.dumps({"mode":"ORIGINAL_UI_RESTORED","console_errors":errors,"title":page.title()},ensure_ascii=False,indent=2),encoding="utf-8")
    browser.close()
print("Original UI browser verification passed")
