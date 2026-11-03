"""Legacy business HTTP smoke against isolated QA database only, sandbox payment only."""

import argparse
import json
import secrets
import time
import urllib.error
import urllib.request

from paths import ROOT

parser = argparse.ArgumentParser()
parser.add_argument("--api", default="http://127.0.0.1:8003")
parser.add_argument("--report", default="reports/rag-upgrade/business-smoke.json")
args = parser.parse_args()
API = args.api
if API not in ("http://127.0.0.1:8003", "http://127.0.0.1:8004", "http://127.0.0.1:8006"):
    raise SystemExit("Only isolated local QA endpoints are accepted")
report_path = (ROOT / args.report).resolve()
if not report_path.is_relative_to(ROOT / "reports"):
    raise SystemExit("Report must remain in project reports")
checks = []


def call(method, path, data=None, token=None, expected=200):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(
        API + path, method=method, data=json.dumps(data).encode() if data is not None else None, headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            code = r.status
            body = json.load(r)
    except urllib.error.HTTPError as e:
        code = e.code
        body = {}
    checks.append({"method": method, "path": path.split("?")[0], "status": code, "expected": expected})
    assert code == expected, checks[-1]
    return body


phone = "139" + str(time.time_ns())[-8:]
password = secrets.token_urlsafe(18)
call("POST", "/api/v1/auth/register", {"phone": phone, "password": password, "nickname": "business-qa"}, expected=201)
login = call("POST", "/api/v1/auth/login", {"phone": phone, "password": password})
token = login.get("access_token") or login.get("accessToken")
call("GET", "/api/v1/auth/me", token=token)
call("GET", "/api/v1/horses")
call("GET", "/api/v1/horses/rag-library?size=100")
call("POST", "/api/v1/gacha/checkin", {}, token)
draw = call("POST", "/api/v1/gacha/draw", {"draw_type": "free"}, token)
assert len(draw["results"]) == 1
call("GET", "/api/v1/gacha/collection", token=token)
call("GET", "/api/v1/collections", token=token)
products = call("GET", "/api/v1/products")
product = next(p for p in products["items"] if p["stock"] > 0)
order = call(
    "POST",
    "/api/v1/orders",
    {
        "items": [{"product_id": product["id"], "quantity": 1}],
        "shipping_address": {
            "name": "测试虚拟收件人",
            "phone": "00000000000",
            "province": "测试",
            "city": "测试",
            "district": "测试",
            "detail": "无实际配送",
        },
    },
    token,
    201,
)
call("GET", "/api/v1/orders/" + order["id"], token=token)
payment = call(
    "POST",
    "/api/v1/payments/create",
    {"order_id": order["id"], "method": "wechat", "amount": order["total_amount"]},
    token,
)
assert payment["payment_url"].startswith("https://sandbox.pay/")
call("POST", "/api/v1/payments/" + payment["payment_id"] + "/simulate-success", {}, token)
call("GET", "/api/v2/projects", expected=401)
call("POST", "/api/v2/research/runs", {"query": "赤兔"}, expected=401)
report_path.write_text(
    json.dumps(
        {"scope": "ISOLATED_DATABASE_COPY", "payment": "SANDBOX_NO_NETWORK", "checks": checks},
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
print(f"{len(checks)} legacy business/security HTTP checks PASS; sandbox only")
