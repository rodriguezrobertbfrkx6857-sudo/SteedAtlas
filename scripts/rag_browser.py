"""Original-site desktop/mobile regression; all output stays in this checkout."""

import argparse
import json

from paths import ROOT
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--phase", default="before", choices=["before", "after"])
parser.add_argument("--web", default="http://127.0.0.1:5173")
args = parser.parse_args()
shots = ROOT / "reports/screenshots/rag-upgrade"
shots.mkdir(parents=True, exist_ok=True)
web = args.web
result = {"phase": args.phase, "pages": [], "errors": []}
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page()
    page.on("pageerror", lambda e: result["errors"].append(str(e)))
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
            response = page.goto(web + route, wait_until="networkidle")
            page.screenshot(path=str(shots / f"{args.phase}-{name}-{device}.png"))
            result["pages"].append(
                {
                    "route": route,
                    "device": device,
                    "status": response.status,
                    "title": page.title(),
                    "overflow": page.evaluate("document.documentElement.scrollWidth>innerWidth"),
                    "links": page.locator("header a").evaluate_all(
                        '(xs)=>xs.map(x=>({text:x.textContent,href:x.getAttribute("href")}))'
                    ),
                }
            )
    browser.close()
(ROOT / f"reports/rag-upgrade/browser-{args.phase}.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps({"pages": len(result["pages"]), "errors": result["errors"]}, ensure_ascii=False))
assert not result["errors"]
