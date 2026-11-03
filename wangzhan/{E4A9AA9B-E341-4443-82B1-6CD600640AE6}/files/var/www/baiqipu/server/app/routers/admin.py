import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.horse import Horse
from app.models.product import Product
from app.models.order import Order
from app.models.user import User
from app.services import shopee
from app.services.auth import get_current_admin_user

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin_user)])


# --- Schemas ---

class HorseCreateIn(BaseModel):
    id: str
    name: str
    title: str
    rarity: str
    image: str
    story: str
    full_story: str = ""
    historical_source: str = ""
    dynasty: str = ""
    owner: str = ""
    trait: str
    traits: list[str] = []
    drop_rate: float = 0.0
    price: float | None = None


class HorseUpdateIn(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    rarity: Optional[str] = None
    image: Optional[str] = None
    story: Optional[str] = None
    full_story: Optional[str] = None
    trait: Optional[str] = None
    traits: Optional[list[str]] = None
    drop_rate: Optional[float] = None
    price: Optional[float] = None


class ProductCreateIn(BaseModel):
    id: str
    name: str
    horse_id: str
    series: str = ""
    price: float
    original_price: float | None = None
    stock: int = 500
    limited_edition: bool = False
    limited_count: int | None = None
    images: list[str] = []
    description: str = ""
    specs: dict = {}
    emotional_points: list[str] = []


class ProductUpdateIn(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    limited_edition: Optional[bool] = None
    description: Optional[str] = None
    specs: Optional[dict] = None
    emotional_points: Optional[list[str]] = None


class OrderUpdateIn(BaseModel):
    status: str  # pending / paid / shipped / completed / cancelled


class UserRoleUpdateIn(BaseModel):
    role: str


class ShopeePublishOptionIn(BaseModel):
    id: int
    label: str
    description: str = ""
    parent_id: int | None = None
    is_leaf: bool | None = None
    tags: list[str] = Field(default_factory=list)


class ShopeePublishConfigUpdateIn(BaseModel):
    shop_id: int | None = None
    default_category_id: int | None = None
    default_logistic_id: int | None = None
    category_options: list[ShopeePublishOptionIn] = Field(default_factory=list)
    logistic_options: list[ShopeePublishOptionIn] = Field(default_factory=list)
    default_weight_kg: float | None = None
    item_status: str = "UNLIST"
    upload_images: bool = True
    notes: str = ""


class ShopeePublishCatalogSyncIn(BaseModel):
    shop_id: int | None = None
    language: str | None = None
    include_categories: bool = True
    include_logistics: bool = True


class ShopeePublishCatalogSyncSummaryOut(BaseModel):
    platform: str
    shop_id: int
    language: str
    auto_refreshed: bool = False
    category_count: int = 0
    logistic_count: int = 0
    category_request_id: str | None = None
    logistic_request_id: str | None = None
    category_request_path: str | None = None
    logistic_request_path: str | None = None


class ShopeePublishCatalogSyncOut(BaseModel):
    config: dict
    synced: ShopeePublishCatalogSyncSummaryOut


def _find_publish_option_by_id(options: list[ShopeePublishOptionIn], option_id: int | None) -> ShopeePublishOptionIn | None:
    if option_id is None:
        return None
    for option in options:
        if option.id == option_id:
            return option
    return None


def _validate_shopee_publish_config_input(data: ShopeePublishConfigUpdateIn) -> None:
    if data.shop_id is not None and data.shop_id <= 0:
        raise HTTPException(status_code=400, detail="shop_id must be a positive integer")
    if data.default_category_id is not None and data.default_category_id <= 0:
        raise HTTPException(status_code=400, detail="default_category_id must be a positive integer")
    if data.default_logistic_id is not None and data.default_logistic_id <= 0:
        raise HTTPException(status_code=400, detail="default_logistic_id must be a positive integer")

    selected_category = _find_publish_option_by_id(data.category_options, data.default_category_id)
    if data.default_category_id is not None:
        if selected_category is None:
            raise HTTPException(status_code=400, detail="default_category_id must exist in category_options")
        if selected_category.is_leaf is False:
            raise HTTPException(status_code=400, detail="default_category_id must reference a leaf category")
        if selected_category.is_leaf is None:
            raise HTTPException(
                status_code=400,
                detail="default_category_id is missing leaf metadata. Sync categories from Shopee or mark the option as leaf.",
            )

    if data.default_logistic_id is not None and data.logistic_options:
        if _find_publish_option_by_id(data.logistic_options, data.default_logistic_id) is None:
            raise HTTPException(status_code=400, detail="default_logistic_id must exist in logistic_options")


# --- Horse Management ---

@router.post("/horses", status_code=201)
def create_horse(data: HorseCreateIn, db: Session = Depends(get_db)):
    existing = db.query(Horse).filter(Horse.id == data.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Horse ID already exists")
    horse = Horse(**data.model_dump())
    db.add(horse)
    db.commit()
    return {"message": "Horse created", "id": horse.id}


@router.put("/horses/{horse_id}")
def update_horse(horse_id: str, data: HorseUpdateIn, db: Session = Depends(get_db)):
    horse = db.query(Horse).filter(Horse.id == horse_id).first()
    if not horse:
        raise HTTPException(status_code=404, detail="Horse not found")
    for key, val in data.model_dump(exclude_none=True).items():
        setattr(horse, key, val)
    db.commit()
    return {"message": "Horse updated", "id": horse_id}


@router.delete("/horses/{horse_id}")
def delete_horse(horse_id: str, db: Session = Depends(get_db)):
    horse = db.query(Horse).filter(Horse.id == horse_id).first()
    if not horse:
        raise HTTPException(status_code=404, detail="Horse not found")
    db.delete(horse)
    db.commit()
    return {"message": "Horse deleted", "id": horse_id}


# --- Product Management ---

@router.post("/products", status_code=201)
def create_product(data: ProductCreateIn, db: Session = Depends(get_db)):
    existing = db.query(Product).filter(Product.id == data.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Product ID already exists")
    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    return {"message": "Product created", "id": product.id}


@router.put("/products/{product_id}")
def update_product(product_id: str, data: ProductUpdateIn, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for key, val in data.model_dump(exclude_none=True).items():
        setattr(product, key, val)
    db.commit()
    return {"message": "Product updated", "id": product_id}


@router.delete("/products/{product_id}")
def delete_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
    return {"message": "Product deleted", "id": product_id}


# --- Order Management ---

@router.get("/orders")
def list_all_orders(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Order)
    if status:
        query = query.filter(Order.status == status)
    total = query.count()
    orders = query.order_by(Order.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return {
        "items": [
            {
                "id": o.id,
                "user_id": o.user_id,
                "total_amount": o.total_amount,
                "status": o.status,
                "payment_method": o.payment_method,
                "item_count": len(o.items) if o.items else 0,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders
        ],
        "total": total,
        "page": page,
    }


@router.put("/orders/{order_id}")
def update_order_status(order_id: str, data: OrderUpdateIn, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = data.status
    db.commit()
    return {"message": "Order status updated", "id": order_id, "status": data.status}


# --- User Management ---

@router.get("/users")
def list_users(
    tier: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if tier:
        query = query.filter(User.tier == tier)
    if role:
        query = query.filter(User.role == role)
    total = query.count()
    users = query.order_by(User.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return {
        "items": [
            {
                "id": u.id,
                "nickname": u.nickname,
                "phone": u.phone,
                "role": u.role,
                "tier": u.tier,
                "purchase_count": u.purchase_count,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
        "total": total,
        "page": page,
        "size": size,
    }


@router.put("/users/{user_id}/role")
def update_user_role(user_id: str, data: UserRoleUpdateIn, db: Session = Depends(get_db)):
    normalized_role = str(data.role or "").strip().lower()
    if normalized_role not in {"user", "operator", "admin"}:
        raise HTTPException(status_code=400, detail="Invalid role")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = normalized_role
    db.commit()
    return {"message": "User role updated", "id": user_id, "role": normalized_role}


@router.get("/shopee/publish-configs")
def list_shopee_publish_configs(db: Session = Depends(get_db)):
    items = shopee.list_publish_configs(db)
    return {
        "items": items,
        "total": len(items),
    }


@router.put("/shopee/publish-configs/{platform}")
def update_shopee_publish_config(
    platform: str,
    data: ShopeePublishConfigUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin_user),
):
    _validate_shopee_publish_config_input(data)
    try:
        config = shopee.upsert_publish_config(
            db,
            platform=platform,
            shop_id=data.shop_id,
            default_category_id=data.default_category_id,
            default_logistic_id=data.default_logistic_id,
            category_options=[item.model_dump() for item in data.category_options],
            logistic_options=[item.model_dump() for item in data.logistic_options],
            default_weight_kg=data.default_weight_kg,
            item_status=data.item_status,
            upload_images=data.upload_images,
            notes=data.notes,
            updated_by_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Shopee request failed: {exc}")
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return shopee.serialize_publish_config(config, platform)


@router.post("/shopee/publish-configs/{platform}/sync-options", response_model=ShopeePublishCatalogSyncOut)
def sync_shopee_publish_catalogs(
    platform: str,
    data: ShopeePublishCatalogSyncIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin_user),
):
    try:
        return shopee.sync_publish_option_catalogs(
            db,
            platform=platform,
            shop_id=data.shop_id,
            language=data.language,
            include_categories=data.include_categories,
            include_logistics=data.include_logistics,
            connected_by_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
