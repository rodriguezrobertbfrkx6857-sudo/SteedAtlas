import random
from dataclasses import dataclass

PITY_THRESHOLD = 50
SOFT_PITY_START = 40

BASE_RATES = {"SSR": 5, "SR": 15, "R": 80}
UP_SSR_RATE = 0.5
FRAGMENT_REWARDS = {"SSR": 60, "SR": 20, "R": 5}
REDEEM_COSTS = {"SSR": 180, "SR": 80, "R": 30}


@dataclass
class GachaPoolItem:
    horse_id: str
    name: str
    rarity: str
    drop_rate: float


DEFAULT_POOL: list[GachaPoolItem] = [
    GachaPoolItem("chitu", "赤兔", "SSR", 2),
    GachaPoolItem("wuzhui", "乌骓", "SSR", 2),
    GachaPoolItem("dilu", "的卢", "SSR", 1),
    GachaPoolItem("jueying", "绝影", "SR", 7),
    GachaPoolItem("hanxue", "汗血", "SR", 8),
    GachaPoolItem("zhuifeng", "追风", "R", 20),
    GachaPoolItem("taxue", "踏雪", "R", 30),
    GachaPoolItem("feidian", "飞电", "R", 30),
]


def calculate_rates(pity_count: int) -> dict[str, float]:
    """Calculate effective rates based on pity count."""
    if pity_count >= PITY_THRESHOLD - 1:
        return {"SSR": 100, "SR": 0, "R": 0}
    if pity_count >= SOFT_PITY_START:
        bonus = (pity_count - SOFT_PITY_START) * 5
        ssr = min(BASE_RATES["SSR"] + bonus, 100)
        sr = max(BASE_RATES["SR"] - bonus * 0.3, 0)
        r = max(100 - ssr - sr, 0)
        return {"SSR": ssr, "SR": sr, "R": r}
    return dict(BASE_RATES)


def draw_once(pity_count: int, pool: list[GachaPoolItem] | None = None) -> GachaPoolItem:
    """Perform a single weighted draw with pity adjustment."""
    if pool is None:
        pool = DEFAULT_POOL

    rates = calculate_rates(pity_count)

    rarity_totals = {"SSR": 0.0, "SR": 0.0, "R": 0.0}
    for item in pool:
        rarity_totals[item.rarity] += item.drop_rate

    adjusted: list[tuple[GachaPoolItem, float]] = []
    for item in pool:
        if rarity_totals[item.rarity] > 0:
            effective = (item.drop_rate / rarity_totals[item.rarity]) * rates[item.rarity]
        else:
            effective = 0
        adjusted.append((item, effective))

    roll = random.random() * 100
    cumulative = 0.0
    for item, rate in adjusted:
        cumulative += rate
        if roll <= cumulative:
            return item

    return pool[0]


def draw_guaranteed_sr(pool: list[GachaPoolItem] | None = None) -> GachaPoolItem:
    if pool is None:
        pool = DEFAULT_POOL

    sr_pool = [item for item in pool if item.rarity == "SR"]
    if not sr_pool:
        sr_pool = [item for item in pool if item.rarity in {"SR", "SSR"}]
    if not sr_pool:
        return pool[0]

    total = sum(item.drop_rate for item in sr_pool)
    roll = random.random() * total
    cumulative = 0.0
    for item in sr_pool:
        cumulative += item.drop_rate
        if roll <= cumulative:
            return item
    return sr_pool[0]


def get_fragment_reward(rarity: str) -> int:
    return FRAGMENT_REWARDS.get(rarity, 0)


def get_redeem_cost(rarity: str) -> int:
    return REDEEM_COSTS.get(rarity, 999)


def _apply_up_pick(
    item: GachaPoolItem,
    pool: list[GachaPoolItem],
    up_horse_id: str | None,
) -> GachaPoolItem:
    if item.rarity != "SSR" or not up_horse_id:
        return item

    up_item = next((candidate for candidate in pool if candidate.horse_id == up_horse_id and candidate.rarity == "SSR"), None)
    if not up_item:
        return item

    if item.horse_id == up_horse_id or random.random() < UP_SSR_RATE:
        return up_item
    return item


def draw_multiple(
    count: int,
    pity_count: int,
    owned: set[str],
    pool: list[GachaPoolItem] | None = None,
    up_horse_id: str | None = None,
) -> list[dict]:
    """Perform multiple draws, returning results with metadata."""
    if pool is None:
        pool = DEFAULT_POOL

    results = []
    current_pity = pity_count

    for _ in range(count):
        item = _apply_up_pick(draw_once(current_pity, pool), pool, up_horse_id)
        is_pity = current_pity >= PITY_THRESHOLD - 1
        is_new = item.horse_id not in owned

        results.append({
            "horse_id": item.horse_id,
            "horse_name": item.name,
            "rarity": item.rarity,
            "is_new": is_new,
            "is_pity": is_pity,
            "is_up": bool(up_horse_id and item.horse_id == up_horse_id),
            "fragments_awarded": 0,
        })

        if item.rarity == "SSR":
            current_pity = 0
        else:
            current_pity += 1

        if is_new:
            owned.add(item.horse_id)

    if count >= 10 and results and not any(result["rarity"] in {"SR", "SSR"} for result in results):
        item = draw_guaranteed_sr(pool)
        is_new = item.horse_id not in owned
        results[-1] = {
            "horse_id": item.horse_id,
            "horse_name": item.name,
            "rarity": item.rarity,
            "is_new": is_new,
            "is_pity": False,
            "is_up": bool(up_horse_id and item.horse_id == up_horse_id),
            "fragments_awarded": 0,
        }
        if is_new:
            owned.add(item.horse_id)

    return results
