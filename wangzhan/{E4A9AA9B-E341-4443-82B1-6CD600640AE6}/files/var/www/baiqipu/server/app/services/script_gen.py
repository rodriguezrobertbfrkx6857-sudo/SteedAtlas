from __future__ import annotations

import json
import uuid
from typing import Any

import httpx

from app.config import get_settings
from app.services.ai_engine import CORPUS_PATH

DEFAULT_SCRIPT_STYLES = ["emotional", "knowledge", "motivational"]


class ScriptGenerationError(ValueError):
    """Raised when the requested horse profile cannot be resolved."""


def load_video_catalog() -> list[dict[str, Any]]:
    with open(CORPUS_PATH, "r", encoding="utf-8") as file:
        docs = json.load(file)

    catalog = []
    for doc in docs:
        metadata = doc.get("metadata", {})
        catalog.append(
            {
                "sequence": int(metadata.get("sequence", len(catalog) + 1)),
                "name": str(metadata.get("name", "")).strip(),
                "figure": str(metadata.get("figure", "")).strip(),
                "source": str(metadata.get("source", "")).strip(),
                "story": str(metadata.get("story", "")).strip(),
                "labels": [str(label).strip() for label in metadata.get("labels", []) if str(label).strip()],
            }
        )

    return sorted(catalog, key=lambda item: item["sequence"])


def resolve_horse_profile(horse_name: str) -> dict[str, Any]:
    normalized = horse_name.strip()
    if not normalized:
        raise ScriptGenerationError("Horse name is required.")

    catalog = load_video_catalog()
    for item in catalog:
        if item["name"] == normalized:
            return item

    lowered = normalized.lower()
    for item in catalog:
        haystack = " ".join([item["name"], item["figure"], item["source"], item["story"]]).lower()
        if lowered in haystack:
            return item

    raise ScriptGenerationError(f"Horse '{horse_name}' not found in video catalog.")


def build_db_horse_profile(horse: Any) -> dict[str, Any]:
    labels = [label for label in horse.traits or [] if label] or [horse.trait]
    source_parts = [horse.dynasty or "", horse.historical_source or ""]
    return {
        "sequence": 0,
        "name": horse.name,
        "figure": horse.owner or "相关历史人物",
        "source": "".join(source_parts).strip() or "项目内置马匹资料",
        "story": horse.full_story or horse.story,
        "labels": labels[:3],
    }


def _extract_response_text(payload: dict[str, Any]) -> str:
    direct_text = payload.get("output_text")
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()

    fragments: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                fragments.append(content["text"])

    return "".join(fragments).strip()


def _normalize_styles(styles: list[str], count: int) -> list[str]:
    unique_styles = [style.strip().lower() for style in styles if style.strip()]
    ordered = []
    for style in unique_styles + DEFAULT_SCRIPT_STYLES:
        if style not in ordered:
            ordered.append(style)
    return ordered[:count]


def _shot_count_for_duration(duration: int) -> int:
    if duration <= 15:
        return 3
    if duration <= 30:
        return 4
    return 5


def _build_fallback_shots(profile: dict[str, Any], style: str, duration: int) -> list[dict[str, Any]]:
    labels = profile["labels"] or ["名马精神"]
    scene_count = _shot_count_for_duration(duration)
    visuals = [
        f"{profile['name']}近景登场，突出“{labels[0]}”气质与中国名马识别度。",
        f"{profile['figure']}与{profile['name']}并肩出场，交代人物关系与时代背景。",
        f"用“{profile['story']}”对应的关键瞬间做主镜头，突出故事记忆点。",
        f"切到标签强化画面：{labels[0]}、{labels[min(1, len(labels) - 1)]}、{labels[min(2, len(labels) - 1)]}。",
        f"收束到百骑谱世界观海报镜头，保留可转商品化和传播的结尾空间。",
    ]
    subtitles = [
        f"{profile['name']}，不是普通坐骑，而是{profile['figure']}的精神投影。",
        f"它出自{profile['source']}，故事核心只有一句：{profile['story']}",
        f"如果把这匹马变成一个人格，它最像{ '、'.join(labels) }。",
        f"这也是百骑谱要讲的，不只是马，而是一种可以被记住的气质。",
        f"当你需要一种力量时，也许答案就藏在{profile['name']}身上。",
    ]
    if style == "knowledge":
        subtitles[0] = f"说到{profile['name']}，先要记住它对应的人物是{profile['figure']}。"
    elif style == "motivational":
        subtitles[0] = f"{profile['name']}的价值，从来不只在速度，而在它代表的{labels[0]}。"

    return [
        {"scene": index + 1, "visual": visuals[index], "subtitle": subtitles[index]}
        for index in range(scene_count)
    ]


def _build_fallback_script(
    profile: dict[str, Any],
    style: str,
    duration: int,
    custom_text: str,
) -> dict[str, Any]:
    labels = profile["labels"] or ["名马精神"]
    label_text = "、".join(labels)
    style = style.lower()

    if style == "knowledge":
        title = f"{profile['name']}是谁的马？一条视频读懂它"
        opening = f"如果要用一匹马读懂{profile['figure']}，往往得先从{profile['name']}说起。"
        body = f"{profile['name']}见于{profile['source']}，最核心的故事是：{profile['story']}。它在百骑谱里代表的是{label_text}。"
        closing = f"记住{profile['name']}，你记住的不只是坐骑，而是中国名马叙事里的一个人格原型。"
    elif style == "motivational":
        title = f"{profile['name']}：把{labels[0]}活成一种力量"
        opening = f"真正能在关键时刻顶住局面的，往往不是热闹，而是像{profile['name']}这样清楚知道自己为何而战。"
        body = f"它对应{profile['figure']}，出处可追到{profile['source']}。一句话看懂它：{profile['story']}。所以{profile['name']}最打动人的地方，在于{label_text}。"
        closing = f"当你也要穿过一段硬仗时，{profile['name']}提醒你的，是别丢掉自己的锋芒和方向。"
    else:
        title = f"如果一种气质有名字，那可能叫{profile['name']}"
        opening = f"有些名字，一出现就带着命运的回响。对很多人来说，{profile['name']}就是这样的存在。"
        body = f"它对应{profile['figure']}，故事来自{profile['source']}：{profile['story']}。所以在百骑谱里，{profile['name']}天然带着{label_text}的情绪重量。"
        closing = f"也许你喜欢的从来不只是马，而是{profile['name']}身上那种仍然愿意向前的气质。"

    if custom_text.strip():
        body = f"{body} 补充表达：{custom_text.strip()}"

    return {
        "title": title,
        "opening": opening,
        "body": body,
        "closing": closing,
        "shots": _build_fallback_shots(profile, style, duration),
    }


def _generate_openai_scripts(
    profile: dict[str, Any],
    styles: list[str],
    count: int,
    duration: int,
    custom_text: str,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        return None, None

    prompt = "\n".join(
        [
            "请你担任“百骑谱”AI视频工厂脚本策划，生成适合短视频的中文口播脚本。",
            "返回 JSON，格式必须是：{\"scripts\":[{\"style\":\"...\",\"title\":\"...\",\"opening\":\"...\",\"body\":\"...\",\"closing\":\"...\",\"shots\":[{\"scene\":1,\"visual\":\"...\",\"subtitle\":\"...\"}]}]}。",
            "不要输出 markdown，不要输出额外解释。",
            f"名马：{profile['name']}",
            f"对应人物：{profile['figure']}",
            f"朝代/出处：{profile['source']}",
            f"一句故事：{profile['story']}",
            f"人格标签：{'、'.join(profile['labels'])}",
            f"目标脚本风格：{', '.join(styles)}",
            f"脚本数量：{count}",
            f"目标时长：{duration}秒",
            f"补充要求：{custom_text or '无'}",
            "每条脚本都要包含可用于分镜的 shots 数组，15秒输出3镜，30秒输出4镜，60秒输出5镜。",
        ]
    )

    payload: dict[str, Any] = {
        "model": settings.OPENAI_MODEL,
        "instructions": "你是一个严谨的中文短视频脚本策划助手。",
        "input": [{"role": "developer", "content": prompt}],
        "max_output_tokens": min(settings.OPENAI_MAX_OUTPUT_TOKENS * 2, 1600),
    }
    if settings.OPENAI_REASONING_EFFORT:
        payload["reasoning"] = {"effort": settings.OPENAI_REASONING_EFFORT}

    endpoint = f"{settings.OPENAI_BASE_URL.rstrip('/')}/responses"
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(endpoint, headers=headers, json=payload, timeout=settings.OPENAI_TIMEOUT_SECONDS)
        response.raise_for_status()
        text = _extract_response_text(response.json())
        data = json.loads(text)
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None, None

    scripts = data.get("scripts")
    if not isinstance(scripts, list):
        return None, None

    normalized: list[dict[str, Any]] = []
    for script in scripts[:count]:
        shots = script.get("shots")
        if not isinstance(shots, list) or not shots:
            return None, None
        normalized.append(
            {
                "title": str(script.get("title", "")).strip(),
                "opening": str(script.get("opening", "")).strip(),
                "body": str(script.get("body", "")).strip(),
                "closing": str(script.get("closing", "")).strip(),
                "style": str(script.get("style", "")).strip().lower() or "emotional",
                "shots": [
                    {
                        "scene": int(shot.get("scene", index + 1)),
                        "visual": str(shot.get("visual", "")).strip(),
                        "subtitle": str(shot.get("subtitle", "")).strip(),
                    }
                    for index, shot in enumerate(shots)
                ],
            }
        )

    if not normalized:
        return None, None

    return normalized, settings.OPENAI_MODEL


def generate_script_variants(
    horse_name: str,
    *,
    history: str = "",
    tags: list[str] | None = None,
    styles: list[str] | None = None,
    count: int = 3,
    duration: int = 30,
    custom_text: str = "",
    profile_override: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    profile = profile_override or resolve_horse_profile(horse_name)
    merged_profile = dict(profile)
    incoming_tags = [tag.strip() for tag in tags or [] if tag.strip()]
    merged_labels = list(dict.fromkeys([*merged_profile.get("labels", []), *incoming_tags]))
    if merged_labels:
        merged_profile["labels"] = merged_labels[:5]
    if history.strip():
        merged_profile["story"] = history.strip()

    normalized_styles = _normalize_styles(styles or DEFAULT_SCRIPT_STYLES, count)
    llm_scripts, model_name = _generate_openai_scripts(
        merged_profile,
        normalized_styles,
        count,
        duration,
        custom_text,
    )

    generation_mode = "llm" if llm_scripts else "template"
    source_scripts = llm_scripts or [
        {
            **_build_fallback_script(merged_profile, style, duration, custom_text),
            "style": style,
        }
        for style in normalized_styles
    ]

    scripts = []
    for style, raw_script in zip(normalized_styles, source_scripts):
        voiceover = " ".join(
            part.strip()
            for part in [raw_script["opening"], raw_script["body"], raw_script["closing"]]
            if part.strip()
        )
        scripts.append(
            {
                "id": f"scr_{uuid.uuid4().hex[:12]}",
                "horse_name": merged_profile["name"],
                "style": raw_script.get("style", style),
                "title": raw_script["title"],
                "opening": raw_script["opening"],
                "body": raw_script["body"],
                "closing": raw_script["closing"],
                "voiceover": voiceover,
                "shots": raw_script["shots"],
                "estimated_seconds": duration,
                "generation_mode": generation_mode,
                "model": model_name,
            }
        )

    return merged_profile, scripts
