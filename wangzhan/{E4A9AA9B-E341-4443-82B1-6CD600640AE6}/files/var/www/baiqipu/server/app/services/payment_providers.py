import hmac
import hashlib
from typing import Dict, Any
from app.config import get_settings

settings = get_settings()

# Simple simulated provider secrets (in production use secure storage)
WECHAT_SECRET = "wechat-sandbox-secret"
ALIPAY_SECRET = "alipay-sandbox-secret"


def _sign_params(params: Dict[str, Any], secret: str) -> str:
    # deterministic simple signature: sort keys, concat k=v, HMAC-SHA256
    items = sorted((k, str(v)) for k, v in params.items())
    s = "&".join(f"{k}={v}" for k, v in items)
    return hmac.new(secret.encode(), s.encode(), hashlib.sha256).hexdigest()


def build_wechat_notify(payment_id: str, amount: float, status: str = "SUCCESS") -> Dict[str, Any]:
    payload = {
        "out_trade_no": payment_id,
        "total_fee": int(amount * 100),
        "result_code": status,
        "time_end": "20260419T120000",
    }
    payload["sign"] = _sign_params(payload, WECHAT_SECRET)
    return payload


def verify_wechat_notify(payload: Dict[str, Any]) -> bool:
    sign = payload.get("sign")
    if not sign:
        return False
    data = {k: v for k, v in payload.items() if k != "sign"}
    return _sign_params(data, WECHAT_SECRET) == sign


def build_alipay_notify(payment_id: str, amount: float, status: str = "TRADE_SUCCESS") -> Dict[str, Any]:
    payload = {
        "out_trade_no": payment_id,
        "total_amount": f"{amount:.2f}",
        "trade_status": status,
        "gmt_payment": "2026-04-19 12:00:00",
    }
    payload["sign"] = _sign_params(payload, ALIPAY_SECRET)
    return payload


def verify_alipay_notify(payload: Dict[str, Any]) -> bool:
    sign = payload.get("sign")
    if not sign:
        return False
    data = {k: v for k, v in payload.items() if k != "sign"}
    return _sign_params(data, ALIPAY_SECRET) == sign
