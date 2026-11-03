"""Frozen asset audit and measured screenshot differences, without modifying media."""

import hashlib
import json
import subprocess

from paths import ROOT
from PIL import Image, ImageChops

prefix = "wangzhan/baiqipu.com-source-20260424-194149/"
files = subprocess.check_output(
    ["git", "ls-tree", "-r", "--name-only", "e30acf7", "--", prefix], cwd=ROOT, text=True
).splitlines()
changes = []
for name in files:
    old = subprocess.check_output(["git", "show", "e30acf7:" + name], cwd=ROOT)
    current = (ROOT / name).read_bytes().replace(b"\r\n", b"\n")
    if hashlib.sha256(old.replace(b"\r\n", b"\n")).digest() != hashlib.sha256(current).digest():
        changes.append(name)
assert changes == [prefix + "index.html"], changes
shots = ROOT / "reports/screenshots/rag-upgrade"
diffs = []
for page in ("home", "chat", "atlas", "factory", "gacha", "collection", "shop", "quiz"):
    for device in ("desktop", "mobile"):
        before = Image.open(shots / f"before-{page}-{device}.png").convert("RGB")
        after = Image.open(shots / f"after-{page}-{device}.png").convert("RGB")
        diff = ImageChops.difference(before, after)
        changed = sum(1 for pixel in diff.getdata() if max(pixel) > 20)
        diffs.append(
            {"page": page, "device": device, "changed_pixel_fraction_gt20": changed / (before.width * before.height)}
        )
report = {
    "frozen_assets_checked": len(files),
    "changed_existing_files": changes,
    "new_file": prefix + "evidence-adapter.js",
    "change": "one script include; scoped evidence panel only",
    "pixel_differences": diffs,
    "note": "Pixel difference is measured, not assumed a style regression; chat status and knowledge panel intentionally change.",
}
(ROOT / "reports/rag-upgrade/visual-preservation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
