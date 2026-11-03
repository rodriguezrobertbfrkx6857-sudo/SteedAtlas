"""Bounded read-only API availability probes. No scraping or access-control workarounds."""

import hashlib
import json
import time
from datetime import datetime, timezone

import httpx
from paths import ROOT

UA = "SteedAtlasEvidence/0.1 (https://github.com/rodriguezrobertbfrkx6857-sudo/baiqipu; research source attribution)"
probes = [
    (
        "wikisource",
        "https://zh.wikisource.org/w/api.php",
        {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "prop": "revisions",
            "rvprop": "ids|timestamp|content|sha1",
            "rvslots": "main",
            "titles": "三國志/卷07",
            "maxlag": 5,
        },
    ),
    (
        "wikidata",
        "https://www.wikidata.org/w/api.php",
        {"action": "wbsearchentities", "search": "赤兔", "language": "zh", "format": "json", "limit": 3},
    ),
    ("huggingface", "https://huggingface.co/api/datasets/gujilab/chinese-classical-corpus", {}),
    ("github", "https://api.github.com/repos/chinese-poetry/chinese-poetry", {}),
    (
        "huggingface-card",
        "https://huggingface.co/datasets/gujilab/chinese-classical-corpus/raw/1979f15b4b749b3601fd9ee3e4111a725c079439/README.md",
        {},
    ),
    ("kaggle", "https://www.kaggle.com/api/v1/datasets/view/qianboao/chinesepoetrydataset", {}),
]
out = ROOT / "runtime/source-probe"
out.mkdir(parents=True, exist_ok=True)
results = []
with httpx.Client(headers={"User-Agent": UA}, timeout=20, follow_redirects=False) as client:
    for name, url, params in probes:
        started = time.monotonic()
        try:
            r = client.get(url, params=params)
            result = {
                "provider": name,
                "url": str(r.url),
                "status": r.status_code,
                "bytes": len(r.content),
                "content_type": r.headers.get("content-type"),
                "response_sha256": hashlib.sha256(r.content).hexdigest(),
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
            if r.status_code == 200:
                (out / (name + ".json")).write_bytes(r.content)
            else:
                result["reason"] = (
                    "RATE_LIMIT" if r.headers.get("x-ratelimit-remaining") == "0" else "HTTP_ACCESS_OR_UPSTREAM_FAILURE"
                )
        except httpx.HTTPError as exc:
            result = {"provider": name, "url": url, "status": "FAILED", "reason": type(exc).__name__}
        result["seconds"] = round(time.monotonic() - started, 3)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        time.sleep(1)
report = ROOT / "reports/rag-upgrade/autonomous"
report.mkdir(parents=True, exist_ok=True)
(report / "provider-probes.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
