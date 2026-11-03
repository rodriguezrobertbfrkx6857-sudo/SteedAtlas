from pydantic import BaseModel
from datetime import datetime


class OrderItemIn(BaseModel):
    product_id: str
    quantity: int = 1


class ShippingAddress(BaseModel):
    name: str
    phone: str
    province: str
    city: str
    district: str
    detail: str


class OrderCreate(BaseModel):
    items: list[OrderItemIn]
    shipping_address: ShippingAddress
    payment_method: str = "wechat"


class OrderOut(BaseModel):
    id: str
    user_id: str
    items: list[dict]
    total_amount: float
    status: str
    payment_method: str
    shipping_address: dict
    created_at: datetime

    model_config = {"from_attributes": True}
