from typing import Any

from app.models.horse import Horse
from app.models.user import User

TIER_LABELS = {
    "new": "新用户",
    "growing": "成长型用户",
    "collector": "收藏家",
}

LEGACY_TIER_MAP = {
    "新用户": "new",
    "成长用户": "growing",
    "收藏家": "collector",
}


def infer_user_tier(
    user: User | None,
    collection_count: int = 0,
    favorite_count: int = 0,
) -> str:
    if user:
        normalized_tier = LEGACY_TIER_MAP.get(user.tier, user.tier)
        if normalized_tier in TIER_LABELS:
            return normalized_tier

    purchase_count = user.purchase_count if user else 0
    if purchase_count >= 3 or collection_count >= 8:
        return "collector"
    if purchase_count >= 1 or collection_count >= 3 or favorite_count >= 3:
        return "growing"
    return "new"


def build_recommendation_strategy(
    user: User | None,
    matched_horse: Horse | None,
    recommended_product: dict[str, Any] | None,
    personality_match: dict[str, Any] | None,
    collection_count: int = 0,
    favorite_count: int = 0,
) -> dict[str, Any]:
    tier = infer_user_tier(user, collection_count=collection_count, favorite_count=favorite_count)
    tier_label = TIER_LABELS[tier]
    horse_name = matched_horse.name if matched_horse else (personality_match or {}).get("horse_name") or "当前这匹名马"

    if tier == "collector":
        title = f"更适合做系列化进阶收藏"
        guidance = f"你已经具备一定收藏深度，建议把 {horse_name} 放进更完整的主题线里考虑，而不是只看单次情绪共鸣。"
        next_action = "优先关注稀有度、历史出处和同主题系列的补齐价值。"
    elif tier == "growing":
        title = "继续扩展你的主题收藏线"
        guidance = f"你已经进入稳定积累阶段，当前这次推荐更适合围绕 {horse_name} 的精神标签继续扩展。"
        next_action = "可以优先补同类型气质的名马，逐步形成个人偏好的收藏脉络。"
    else:
        title = "先从一匹最有共鸣的名马开始"
        guidance = f"你当前更适合先建立第一层情感连接，先从 {horse_name} 这种最容易产生代入感的选择入手。"
        next_action = "先看故事和精神标签，再决定是否延伸到商品或收藏。"

    if recommended_product:
        next_action = f"{next_action} 如果想落到实物体验，可以继续看 {recommended_product['name']}。"

    return {
        "tier": tier,
        "tier_label": tier_label,
        "title": title,
        "guidance": guidance,
        "next_action": next_action,
        "collection_count": collection_count,
    }
