from typing import Any

from app.models.horse import Horse

PERSONALITY_ARCHETYPES = [
    {
        "label": "高压突围",
        "horse_name": "乌骓",
        "keywords": ["压力", "低谷", "扛住", "撑住", "焦虑", "疲惫", "困难", "逆境"],
        "traits": ["逆境", "韧性", "爆发"],
        "summary_template": "你现在更像是在高压环境里寻找稳定支点，适合用 {horse_name} 这种带有逆境突围气质的名马来做情绪映照。",
    },
    {
        "label": "守护担当",
        "horse_name": "赤兔",
        "keywords": ["责任", "守护", "承诺", "带队", "担当", "家人", "可靠", "信任"],
        "traits": ["忠诚", "担当", "守护"],
        "summary_template": "你提到的状态更偏向承担与守护，{horse_name} 身上的忠义和担当，会更贴近你当下想要确认的价值感。",
    },
    {
        "label": "等待转机",
        "horse_name": "的卢",
        "keywords": ["迷茫", "转机", "机会", "选择", "下一步", "方向", "犹豫", "突破口"],
        "traits": ["机遇", "转机", "判断"],
        "summary_template": "你现在更需要的是从不确定里抓住转机，{horse_name} 代表的就是在关键时刻完成突围与转向。",
    },
    {
        "label": "长期主义",
        "horse_name": "汗血",
        "keywords": ["坚持", "长期", "积累", "耐心", "长期主义", "慢慢来", "远方", "目标"],
        "traits": ["耐力", "远志", "持续"],
        "summary_template": "从你的表达里能看出更长期主义的一面，{horse_name} 这种强调耐力和远志的名马更容易形成稳定陪伴。",
    },
    {
        "label": "冷静执行",
        "horse_name": "绝影",
        "keywords": ["冷静", "执行", "效率", "判断", "节奏", "推进", "专注", "理性"],
        "traits": ["速度", "执行", "判断"],
        "summary_template": "你更需要一种冷静且能持续推进的力量，{horse_name} 对应的是清醒判断和稳定执行的状态。",
    },
]


def assess_personality_context(
    user_text: str,
    matched_horse: Horse | None = None,
    hits: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    normalized = user_text.strip()
    if not normalized:
        return None

    scored_candidates: list[tuple[int, dict[str, Any]]] = []
    for archetype in PERSONALITY_ARCHETYPES:
        hit_keywords = [keyword for keyword in archetype["keywords"] if keyword in normalized]
        if hit_keywords:
            scored_candidates.append((len(hit_keywords), {**archetype, "hit_keywords": hit_keywords}))

    scored_candidates.sort(key=lambda item: item[0], reverse=True)
    best_match = scored_candidates[0][1] if scored_candidates else None

    horse_name = matched_horse.name if matched_horse else (best_match["horse_name"] if best_match else None)
    if not horse_name and hits:
        horse_name = hits[0].get("metadata", {}).get("name")

    if best_match:
        return {
            "label": best_match["label"],
            "horse_name": horse_name or best_match["horse_name"],
            "signals": best_match["traits"],
            "keywords": best_match["hit_keywords"][:3],
            "summary": best_match["summary_template"].format(horse_name=horse_name or best_match["horse_name"]),
            "confidence": "high" if len(best_match["hit_keywords"]) >= 2 else "medium",
        }

    if matched_horse:
        return {
            "label": matched_horse.trait,
            "horse_name": matched_horse.name,
            "signals": matched_horse.traits or [matched_horse.trait],
            "keywords": [],
            "summary": f"虽然你这次表达里没有特别强的情绪关键词，但从整体语境看，{matched_horse.name} 的“{matched_horse.trait}”仍然是最贴近的气质映射。",
            "confidence": "low",
        }

    return None
