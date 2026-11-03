"""Users API - User profile management and tier classification."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserOut, UserUpdate, UserProfileOut
from app.services.auth import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserProfileOut)
def get_user_profile(
    user: User = Depends(get_current_user),
):
    """Get current user profile with full details."""
    return UserProfileOut(
        id=user.id,
        nickname=user.nickname,
        avatar=user.avatar,
        role=user.role,
        tier=user.tier,
        purchase_count=user.purchase_count,
        phone=user.phone,
        checkin_streak=user.checkin_streak or 0,
        total_checkins=user.total_checkins or 0,
        last_checkin_date=user.last_checkin_date.isoformat() if user.last_checkin_date else None,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@router.patch("/me", response_model=UserOut)
def update_user_profile(
    data: UserUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update current user profile."""
    if data.nickname is not None:
        user.nickname = data.nickname
    if data.avatar is not None:
        user.avatar = data.avatar
    if data.phone is not None:
        # Check if phone is already taken
        existing = db.query(User).filter(
            User.phone == data.phone,
            User.id != user.id,
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Phone number already registered")
        user.phone = data.phone

    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/me/stats", response_model=dict)
def get_user_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user statistics including collection progress."""
    from app.models.gacha import Collection
    from app.models.horse import Horse
    from app.models.order import Order

    total_horses = db.query(Horse).count()
    owned_count = db.query(Collection).filter(
        Collection.user_id == user.id
    ).distinct(Collection.horse_id).count()

    order_count = db.query(Order).filter(
        Order.user_id == user.id
    ).count()

    total_spent = db.query(Order).filter(
        Order.user_id == user.id,
        Order.status == "paid"
    ).with_entities(func.sum(Order.total_amount)).scalar() or 0

    return {
        "collection": {
            "owned": owned_count,
            "total": total_horses,
            "percentage": round(owned_count / max(total_horses, 1) * 100, 1),
        },
        "activity": {
            "checkin_streak": user.checkin_streak or 0,
            "total_checkins": user.total_checkins or 0,
        },
        "purchases": {
            "order_count": order_count,
            "total_spent": float(total_spent),
        },
        "tier": user.tier,
    }


@router.get("/me/tier", response_model=dict)
def get_user_tier(
    user: User = Depends(get_current_user),
):
    """Get user tier information and next tier requirements."""
    tier_descriptions = {
        "new": {
            "name": "新用户",
            "description": "刚加入百骑谱的探索者",
            "next_tier": "growing",
            "next_requirement": "完成首次购买或收藏3匹马",
        },
        "growing": {
            "name": "成长中",
            "description": "正在建立自己的马匹收藏",
            "next_tier": "collector",
            "next_requirement": "收藏10匹马或累计消费500元",
        },
        "collector": {
            "name": "收藏家",
            "description": "百骑谱的资深爱好者",
            "next_tier": None,
            "next_requirement": None,
        },
    }

    tier_info = tier_descriptions.get(user.tier, tier_descriptions["new"])

    return {
        "current_tier": user.tier,
        "tier_name": tier_info["name"],
        "description": tier_info["description"],
        "next_tier": tier_info["next_tier"],
        "next_requirement": tier_info["next_requirement"],
    }


@router.get("/{user_id}", response_model=UserOut)
def get_user_by_id(
    user_id: str,
    db: Session = Depends(get_db),
):
    """Get public user profile by ID (limited info)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserOut.model_validate(user)
