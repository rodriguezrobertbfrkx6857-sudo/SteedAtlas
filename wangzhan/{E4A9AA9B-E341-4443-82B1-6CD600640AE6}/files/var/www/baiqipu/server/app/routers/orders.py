import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.product import Product
from app.models.order import Order
from app.schemas.order import OrderCreate, OrderOut
from app.services.auth import get_current_user

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderOut, status_code=201)
def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order_items = []
    total = 0.0

    for item in data.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        if product.stock < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {product.name}")

        subtotal = product.price * item.quantity
        total += subtotal
        order_items.append({
            "product_id": product.id,
            "name": product.name,
            "price": product.price,
            "quantity": item.quantity,
            "subtotal": subtotal,
        })

        product.stock -= item.quantity

    order = Order(
        id=f"ord_{uuid.uuid4().hex[:12]}",
        user_id=user.id,
        items=order_items,
        total_amount=total,
        payment_method=data.payment_method,
        shipping_address=data.shipping_address.model_dump(),
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    return OrderOut.model_validate(order)


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderOut.model_validate(order)


@router.get("", response_model=list[OrderOut])
def list_orders(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Order).filter(Order.user_id == user.id)
    
    if status:
        query = query.filter(Order.status == status)
    
    orders = (
        query
        .order_by(Order.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return [OrderOut.model_validate(o) for o in orders]


@router.patch("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(
    order_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status not in ["pending", "paid"]:
        raise HTTPException(status_code=400, detail="Cannot cancel order in current status")
    
    # Restore stock
    for item in order.items:
        product = db.query(Product).filter(Product.id == item["product_id"]).first()
        if product:
            product.stock += item["quantity"]
    
    order.status = "cancelled"
    db.commit()
    db.refresh(order)
    
    return OrderOut.model_validate(order)
