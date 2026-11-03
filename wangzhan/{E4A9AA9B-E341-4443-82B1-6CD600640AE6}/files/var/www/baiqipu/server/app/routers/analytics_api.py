from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.user import User
from app.models.order import Order
from app.models.gacha import GachaRecord, Collection
from app.models.horse import Horse
from app.models.product import Product

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
def get_overview(db: Session = Depends(get_db)):
    total_users = db.query(User).count()
    total_orders = db.query(Order).count()
    total_revenue = db.query(func.sum(Order.total_amount)).scalar() or 0
    total_gacha_draws = db.query(GachaRecord).count()
    total_collections = db.query(Collection).count()
    total_horses = db.query(Horse).count()
    total_products = db.query(Product).count()

    return {
        "total_users": total_users,
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "total_gacha_draws": total_gacha_draws,
        "total_collections": total_collections,
        "total_horses": total_horses,
        "total_products": total_products,
    }


@router.get("/funnel")
def get_funnel(db: Session = Depends(get_db)):
    total_users = db.query(User).count()
    users_with_gacha = db.query(GachaRecord.user_id).distinct().count()
    users_with_orders = db.query(Order.user_id).distinct().count()
    paid_orders = db.query(Order).filter(Order.status.in_(["paid", "shipped", "completed"])).count()

    return {
        "steps": [
            {"step": "注册用户", "count": total_users},
            {"step": "参与抽卡", "count": users_with_gacha},
            {"step": "创建订单", "count": users_with_orders},
            {"step": "完成支付", "count": paid_orders},
        ]
    }


@router.get("/user-tiers")
def get_user_tiers(db: Session = Depends(get_db)):
    tiers = db.query(User.tier, func.count(User.id)).group_by(User.tier).all()
    return {"tiers": [{"tier": t, "count": c} for t, c in tiers]}


@router.get("/gacha-stats")
def get_gacha_stats(db: Session = Depends(get_db)):
    total_draws = db.query(GachaRecord).count()
    ssr_draws = db.query(GachaRecord).filter(GachaRecord.rarity == "SSR").count()
    sr_draws = db.query(GachaRecord).filter(GachaRecord.rarity == "SR").count()
    r_draws = db.query(GachaRecord).filter(GachaRecord.rarity == "R").count()

    popular_horses = (
        db.query(Collection.horse_id, Horse.name, func.count(Collection.id))
        .join(Horse, Collection.horse_id == Horse.id)
        .group_by(Collection.horse_id, Horse.name)
        .order_by(func.count(Collection.id).desc())
        .limit(10)
        .all()
    )

    return {
        "total_draws": total_draws,
        "by_rarity": {"SSR": ssr_draws, "SR": sr_draws, "R": r_draws},
        "ssr_rate": round(ssr_draws / max(total_draws, 1) * 100, 2),
        "popular_horses": [
            {"horse_id": hid, "name": name, "collection_count": cnt}
            for hid, name, cnt in popular_horses
        ],
    }


@router.get("/order-stats")
def get_order_stats(db: Session = Depends(get_db)):
    by_status = db.query(Order.status, func.count(Order.id)).group_by(Order.status).all()
    avg_amount = db.query(func.avg(Order.total_amount)).scalar() or 0

    return {
        "by_status": {s: c for s, c in by_status},
        "average_order_amount": round(avg_amount, 2),
    }


@router.get("/product-ranking")
def get_product_ranking(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return {
        "products": [
            {
                "id": p.id,
                "name": p.name,
                "price": p.price,
                "stock": p.stock,
                "sold": (p.limited_count or 500) - p.stock if p.limited_count else 500 - p.stock,
            }
            for p in products
        ]
    }
