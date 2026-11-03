import uuid
from datetime import datetime
from typing import Dict

_payments: Dict[str, dict] = {}


def create_payment(order_id: str, method: str = "wechat", amount: float = 0.0) -> dict:
    payment_id = f"pay_{uuid.uuid4().hex[:12]}"
    provider = method.lower()
    url = f"https://sandbox.pay/{provider}/{payment_id}?order={order_id}&amount={int(amount*100)}"
    task = {
        "payment_id": payment_id,
        "order_id": order_id,
        "provider": provider,
        "amount": amount,
        "payment_url": url,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
    }
    _payments[payment_id] = task
    return task


def get_payment(payment_id: str) -> dict | None:
    return _payments.get(payment_id)


def set_payment_status(payment_id: str, status: str) -> bool:
    p = _payments.get(payment_id)
    if not p:
        return False
    p["status"] = status
    return True
