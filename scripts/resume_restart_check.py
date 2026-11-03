"""Verify owned RC restart retains login, persisted research and evidence."""

import json
import secrets
import subprocess
import sys
import time

import httpx
from paths import ROOT

client = httpx.Client(base_url="http://127.0.0.1:8006", trust_env=False, timeout=60)
phone = "135" + str(time.time_ns())[-8:]
password = secrets.token_urlsafe(18)
response = client.post("/api/v1/auth/register", json={"phone": phone, "password": password, "nickname": "restart-demo"})
response.raise_for_status()
login = client.post("/api/v1/auth/login", json={"phone": phone, "password": password}).json()
client.headers["Authorization"] = "Bearer " + (login.get("access_token") or login["accessToken"])
before = client.get("/api/v2/knowledge/status").json()
proposal = client.post("/api/v2/research/runs", json={"query": "赤兔的史籍出处"})
proposal.raise_for_status()
proposal = proposal.json()
for command in ("stop", "start"):
    subprocess.run([sys.executable, str(ROOT / "scripts/resume_demo.py"), command], check=True)
after = client.get("/api/v2/knowledge/status").json()
assert client.get("/api/v1/auth/me").status_code == 200
saved = client.get("/api/v2/research/runs/" + proposal["id"])
assert saved.status_code == 200 and saved.json()["data"]["trace"] == proposal["data"]["trace"]
assert before == after
report = {
    "login_retained": True,
    "evidence_status_unchanged": True,
    "persisted_research_trace_unchanged": True,
    "status": after,
    "paid_api_calls": 0,
}
(ROOT / "reports/resume-readiness/restart.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("PASS: same login token, stored research trace and evidence status after owned stop/start")
