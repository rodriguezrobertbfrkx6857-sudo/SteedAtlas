from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, desc, distinct, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.gacha import Collection, GachaFragment, GachaRecord
from app.models.horse import Horse
from app.models.user import User
from app.schemas.gacha import (
    CheckinActionOut,
    CheckinRewardOut,
    CheckinStatusOut,
    CollectionItem,
    CollectionOut,
    GachaDrawRequest,
    GachaDrawResult,
    GachaExchangeOut,
    GachaExchangeRequest,
    GachaFragmentItem,
    GachaFragmentsOut,
    LeaderboardEntryOut,
    LeaderboardOut,
)
from app.services.auth import get_current_user, get_optional_user
from app.services.gacha_engine import DEFAULT_POOL, draw_multiple, get_fragment_reward, get_redeem_cost

router = APIRouter(prefix="/gacha", tags=["gacha"])

ACHIEVEMENTS = [
    {"name": "初阶收藏家", "required": 10, "reward": "解锁收藏头像框"},
    {"name": "进阶收藏家", "required": 30, "reward": "解锁稀有马场背景"},
    {"name": "传奇收藏家", "required": 100, "reward": "解锁传奇巡游称号"},
]

CHECKIN_REWARDS = [
    {"day": 1, "reward": "单抽券", "reward_type": "draw"},
    {"day": 2, "reward": "50 积分", "reward_type": "points"},
    {"day": 3, "reward": "单抽券", "reward_type": "draw"},
    {"day": 4, "reward": "100 积分", "reward_type": "points"},
    {"day": 5, "reward": "SR 展示徽章", "reward_type": "badge"},
    {"day": 6, "reward": "200 积分", "reward_type": "points"},
    {"day": 7, "reward": "十连券", "reward_type": "draw_ten"},
]


def _today_local() -> date:
    return datetime.now().astimezone().date()


def _serialize_reward(reward: dict | None) -> CheckinRewardOut | None:
    if reward is None:
        return None
    return CheckinRewardOut(**reward)


def _get_cycle_length() -> int:
    return max(len(CHECKIN_REWARDS), 1)


def _calculate_achievements(owned_count: int) -> list[dict]:
    return [
        {
            **achievement,
            "current": owned_count,
            "unlocked": owned_count >= achievement["required"],
        }
        for achievement in ACHIEVEMENTS
    ]


def _pool_item_map() -> dict[str, object]:
    return {item.horse_id: item for item in DEFAULT_POOL}


def _serialize_fragments(db: Session, user_id: str) -> list[GachaFragmentItem]:
    pool_map = _pool_item_map()
    fragment_rows = db.query(GachaFragment).filter(GachaFragment.user_id == user_id).all()
    quantities = {row.horse_id: int(row.quantity or 0) for row in fragment_rows}
    horse_ids = set(pool_map) | set(quantities)
    horses = db.query(Horse).filter(Horse.id.in_(horse_ids)).all() if horse_ids else []
    horse_map = {horse.id: horse for horse in horses}

    items: list[GachaFragmentItem] = []
    for horse_id in sorted(horse_ids, key=lambda item: (horse_map.get(item).rarity if horse_map.get(item) else pool_map.get(item).rarity if pool_map.get(item) else "Z", item)):
        horse = horse_map.get(horse_id)
        pool_item = pool_map.get(horse_id)
        rarity = horse.rarity if horse else pool_item.rarity if pool_item else "R"
        items.append(
            GachaFragmentItem(
                horse_id=horse_id,
                horse_name=horse.name if horse else pool_item.name if pool_item else horse_id,
                rarity=rarity,
                quantity=quantities.get(horse_id, 0),
                redeem_cost=get_redeem_cost(rarity),
            )
        )
    return items


def _serialize_collection(db: Session, user_id: str) -> list[CollectionItem]:
    records = (
        db.query(Collection, Horse)
        .join(Horse, Collection.horse_id == Horse.id)
        .filter(Collection.user_id == user_id)
        .all()
    )
    return [
        CollectionItem(
            horse_id=collection.horse_id,
            horse_name=horse.name,
            rarity=horse.rarity,
            source=collection.source,
            obtained_at=collection.obtained_at,
        )
        for collection, horse in records
    ]


def _get_fragment_record(db: Session, user_id: str, horse_id: str) -> GachaFragment:
    record = (
        db.query(GachaFragment)
        .filter(GachaFragment.user_id == user_id, GachaFragment.horse_id == horse_id)
        .first()
    )
    if record:
        return record

    record = GachaFragment(
        id=f"gf_{uuid.uuid4().hex[:12]}",
        user_id=user_id,
        horse_id=horse_id,
        quantity=0,
    )
    db.add(record)
    return record


def _build_collection_progress(db: Session, owned_count: int) -> dict:
    total_horses = db.query(Horse).count()
    return {
        "owned": owned_count,
        "total": total_horses,
        "percentage": round(owned_count / max(total_horses, 1) * 100),
    }


def _build_checkin_status(user: User, today: date | None = None) -> CheckinStatusOut:
    today = today or _today_local()
    streak = int(getattr(user, "checkin_streak", 0) or 0)
    total_checkins = int(getattr(user, "total_checkins", 0) or 0)
    last_checkin_date = getattr(user, "last_checkin_date", None)
    checked_today = bool(last_checkin_date == today)
    cycle_length = _get_cycle_length()
    if checked_today and streak > 0:
        completed_cycle_days = ((streak - 1) % cycle_length) + 1
    else:
        completed_cycle_days = streak % cycle_length
    next_cycle_day = (completed_cycle_days % cycle_length) + 1
    next_reward = next((item for item in CHECKIN_REWARDS if item["day"] == next_cycle_day), None)
    return CheckinStatusOut(
        streak=streak,
        total_checkins=total_checkins,
        last_checkin_date=last_checkin_date,
        checked_today=checked_today,
        completed_cycle_days=completed_cycle_days,
        next_cycle_day=next_cycle_day,
        rewards=[CheckinRewardOut(**item) for item in CHECKIN_REWARDS],
        next_reward=_serialize_reward(next_reward),
    )


def _get_pity_count(db: Session, user_id: str) -> int:
    last_ssr = (
        db.query(GachaRecord)
        .filter(GachaRecord.user_id == user_id, GachaRecord.rarity == "SSR")
        .order_by(GachaRecord.created_at.desc())
        .first()
    )
    if last_ssr:
        return (
            db.query(GachaRecord)
            .filter(GachaRecord.user_id == user_id, GachaRecord.created_at > last_ssr.created_at)
            .count()
        )
    return db.query(GachaRecord).filter(GachaRecord.user_id == user_id).count()


@router.post("/draw", response_model=GachaDrawResult)
def draw(
    req: GachaDrawRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    count = 10 if req.draw_type == "ten" else 1
    total_since_ssr = _get_pity_count(db, user.id)
    owned_records = db.query(Collection.horse_id).filter(Collection.user_id == user.id).all()
    owned = {record.horse_id for record in owned_records}
    results = draw_multiple(count, total_since_ssr, owned, up_horse_id=req.up_horse_id)

    new_pity = total_since_ssr
    fragment_records: dict[str, GachaFragment] = {}
    for result in results:
        record = GachaRecord(
            id=f"g_{uuid.uuid4().hex[:12]}",
            user_id=user.id,
            horse_id=result["horse_id"],
            rarity=result["rarity"],
            draw_type=req.draw_type,
            pity_count=new_pity,
        )
        db.add(record)

        if result["is_new"]:
            db.add(
                Collection(
                    id=f"c_{uuid.uuid4().hex[:12]}",
                    user_id=user.id,
                    horse_id=result["horse_id"],
                    source="gacha",
                )
            )
            result["fragments_awarded"] = 0
        else:
            fragments_awarded = get_fragment_reward(result["rarity"])
            fragment_record = fragment_records.get(result["horse_id"])
            if fragment_record is None:
                fragment_record = _get_fragment_record(db, user.id, result["horse_id"])
                fragment_records[result["horse_id"]] = fragment_record
            fragment_record.quantity = int(fragment_record.quantity or 0) + fragments_awarded
            result["fragments_awarded"] = fragments_awarded

        new_pity = 0 if result["rarity"] == "SSR" else new_pity + 1

    db.commit()

    total_owned = db.query(Collection).filter(Collection.user_id == user.id).count()
    unlocked = [
        {"name": achievement["name"], "required": achievement["required"], "reward": achievement["reward"], "unlocked": True}
        for achievement in ACHIEVEMENTS
        if total_owned >= achievement["required"]
    ]

    return GachaDrawResult(
        results=results,
        pity_count=new_pity,
        collection_progress=_build_collection_progress(db, total_owned),
        new_achievements=unlocked,
        fragments=_serialize_fragments(db, user.id),
    )


@router.get("/collection", response_model=CollectionOut)
def get_collection(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    owned_items = _serialize_collection(db, user.id)
    owned_count = len(owned_items)

    return CollectionOut(
        owned_horses=owned_items,
        progress=_build_collection_progress(db, owned_count),
        achievements=_calculate_achievements(owned_count),
        pity_count=_get_pity_count(db, user.id),
        fragments=_serialize_fragments(db, user.id),
    )


@router.get("/fragments", response_model=GachaFragmentsOut)
def get_fragments(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return GachaFragmentsOut(fragments=_serialize_fragments(db, user.id))


@router.post("/exchange", response_model=GachaExchangeOut)
def exchange_fragment(
    req: GachaExchangeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    horse = db.query(Horse).filter(Horse.id == req.horse_id).first()
    if not horse:
        raise HTTPException(status_code=404, detail="名马不存在。")

    existing = (
        db.query(Collection)
        .filter(Collection.user_id == user.id, Collection.horse_id == req.horse_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="这匹名马已经在你的图鉴里。")

    cost = get_redeem_cost(horse.rarity)
    fragment_record = _get_fragment_record(db, user.id, req.horse_id)
    if int(fragment_record.quantity or 0) < cost:
        raise HTTPException(status_code=409, detail=f"{horse.name} 碎片不足，还需要 {cost - int(fragment_record.quantity or 0)} 个。")

    fragment_record.quantity = int(fragment_record.quantity or 0) - cost
    db.add(
        Collection(
            id=f"c_{uuid.uuid4().hex[:12]}",
            user_id=user.id,
            horse_id=req.horse_id,
            source="fragment",
        )
    )
    db.commit()

    owned_items = _serialize_collection(db, user.id)
    return GachaExchangeOut(
        owned_horses=owned_items,
        progress=_build_collection_progress(db, len(owned_items)),
        pity_count=_get_pity_count(db, user.id),
        fragments=_serialize_fragments(db, user.id),
        message=f"已用 {cost} 个碎片兑换 {horse.name}。",
    )


@router.get("/checkin/status", response_model=CheckinStatusOut)
def get_checkin_status(user: User = Depends(get_current_user)):
    return _build_checkin_status(user)


@router.post("/checkin", response_model=CheckinActionOut)
def perform_checkin(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = _today_local()
    status_before = _build_checkin_status(user, today=today)
    if status_before.checked_today:
        return CheckinActionOut(
            status=status_before,
            reward=None,
            just_checked=False,
            message="今天已经签到过了。",
        )

    yesterday = today.fromordinal(today.toordinal() - 1)
    last_checkin_date = getattr(user, "last_checkin_date", None)
    previous_streak = int(getattr(user, "checkin_streak", 0) or 0)
    if last_checkin_date == yesterday:
        user.checkin_streak = previous_streak + 1
    else:
        user.checkin_streak = 1
    user.total_checkins = int(getattr(user, "total_checkins", 0) or 0) + 1
    user.last_checkin_date = today
    db.add(user)
    db.commit()
    db.refresh(user)

    current_day = ((int(user.checkin_streak) - 1) % _get_cycle_length()) + 1
    reward = next((item for item in CHECKIN_REWARDS if item["day"] == current_day), None)
    return CheckinActionOut(
        status=_build_checkin_status(user, today=today),
        reward=_serialize_reward(reward),
        just_checked=True,
        message="今日签到完成。",
    )


@router.get("/leaderboard", response_model=LeaderboardOut)
def get_leaderboard(
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    collection_stats = (
        db.query(
            Collection.user_id.label("user_id"),
            func.count(distinct(Collection.horse_id)).label("total_owned"),
        )
        .group_by(Collection.user_id)
        .subquery()
    )
    draw_stats = (
        db.query(
            GachaRecord.user_id.label("user_id"),
            func.count(GachaRecord.id).label("total_draws"),
            func.coalesce(func.sum(case((GachaRecord.rarity == "SSR", 1), else_=0)), 0).label("ssr_count"),
        )
        .group_by(GachaRecord.user_id)
        .subquery()
    )

    rows = (
        db.query(
            User.id.label("user_id"),
            User.nickname.label("nickname"),
            User.avatar.label("avatar"),
            func.coalesce(collection_stats.c.total_owned, 0).label("total_owned"),
            func.coalesce(draw_stats.c.ssr_count, 0).label("ssr_count"),
            func.coalesce(draw_stats.c.total_draws, 0).label("total_draws"),
            func.coalesce(User.checkin_streak, 0).label("checkin_streak"),
            func.coalesce(User.total_checkins, 0).label("total_checkins"),
        )
        .outerjoin(collection_stats, collection_stats.c.user_id == User.id)
        .outerjoin(draw_stats, draw_stats.c.user_id == User.id)
        .order_by(
            desc(func.coalesce(collection_stats.c.total_owned, 0)),
            desc(func.coalesce(draw_stats.c.ssr_count, 0)),
            desc(func.coalesce(draw_stats.c.total_draws, 0)),
            desc(func.coalesce(User.total_checkins, 0)),
            User.created_at.asc(),
        )
        .all()
    )

    ranked_rows = [
        row
        for row in rows
        if int(row.total_owned or 0) > 0 or int(row.total_draws or 0) > 0 or int(row.total_checkins or 0) > 0
    ]
    entries: list[LeaderboardEntryOut] = []
    current_user_rank: LeaderboardEntryOut | None = None

    for index, row in enumerate(ranked_rows, start=1):
        entry = LeaderboardEntryOut(
            rank=index,
            user_id=str(row.user_id),
            nickname=str(row.nickname or f"Player {index}"),
            avatar=str(row.avatar or ""),
            total_owned=int(row.total_owned or 0),
            ssr_count=int(row.ssr_count or 0),
            total_draws=int(row.total_draws or 0),
            checkin_streak=int(row.checkin_streak or 0),
            total_checkins=int(row.total_checkins or 0),
            is_current_user=bool(current_user and current_user.id == row.user_id),
        )
        if index <= limit:
            entries.append(entry)
        if current_user and current_user.id == row.user_id:
            current_user_rank = entry

    return LeaderboardOut(
        updated_at=datetime.now(UTC),
        limit=limit,
        items=entries,
        current_user_rank=current_user_rank,
    )
