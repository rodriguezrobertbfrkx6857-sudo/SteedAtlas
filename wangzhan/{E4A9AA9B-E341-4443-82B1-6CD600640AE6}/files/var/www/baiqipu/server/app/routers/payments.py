from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth import get_current_user, get_optional_user
from app.services import payment as payment_service
from app.services import payment_providers
from fastapi import Body

router = APIRouter(prefix="/payments", tags=["payments"])


class PaymentCreateIn(BaseModel):
    order_id: str
    method: str = "wechat"
    amount: float | None = None


class PaymentOut(BaseModel):
    payment_id: str
    order_id: str
    provider: str
    amount: float
    payment_url: str
    status: str
    created_at: str


@router.post("/create", response_model=PaymentOut)
def create_payment(req: PaymentCreateIn, db: Session = Depends(get_db), user=Depends(get_optional_user)):
    # In production integrate WeChat/Alipay SDKs here. This is a sandbox stub.
    amount = req.amount or 0.0
    task = payment_service.create_payment(req.order_id, req.method, amount)
    return PaymentOut(**task)


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: str, db: Session = Depends(get_db), user=Depends(get_optional_user)):
    p = payment_service.get_payment(payment_id)
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    return PaymentOut(**p)


@router.post("/{payment_id}/simulate-success")
def simulate_success(payment_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ok = payment_service.set_payment_status(payment_id, "paid")
    if not ok:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {"payment_id": payment_id, "status": "paid"}


@router.post("/{payment_id}/notify/{provider}")
def provider_notify(payment_id: str, provider: str, payload: dict = Body(...), db: Session = Depends(get_db)):
    # Accept simulated provider notification and verify signature
    provider = provider.lower()
    p = payment_service.get_payment(payment_id)
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")

    verified = False
    if provider == "wechat":
        verified = payment_providers.verify_wechat_notify(payload)
    elif provider == "alipay":
        verified = payment_providers.verify_alipay_notify(payload)
    else:
        raise HTTPException(status_code=400, detail="Unknown provider")

    if not verified:
        raise HTTPException(status_code=400, detail="Signature verification failed")

    # mark as paid for simulation
    payment_service.set_payment_status(payment_id, "paid")
    return {"payment_id": payment_id, "status": "paid", "provider": provider}


@router.get("/{payment_id}/simulate-notify/{provider}")
def simulate_provider_notify(payment_id: str, provider: str, db: Session = Depends(get_db)):
    provider = provider.lower()
    p = payment_service.get_payment(payment_id)
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")

    amount = p.get("amount", 0.0)
    if provider == "wechat":
        payload = payment_providers.build_wechat_notify(payment_id, amount)
    elif provider == "alipay":
        payload = payment_providers.build_alipay_notify(payment_id, amount)
    else:
        raise HTTPException(status_code=400, detail="Unknown provider")

    return {"simulate_payload": payload}
