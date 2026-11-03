import json
import math
import os
import re
import uuid
from collections import Counter
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.gacha import Collection
from app.models.horse import Horse
from app.models.product import Product
from app.models.user import User
from app.services.personality import assess_personality_context
from app.services.recommend import build_recommendation_strategy

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
CORPUS_PATH = os.path.join(DATA_DIR, "corpus.json")
VDB_PATH = os.path.join(DATA_DIR, "vectordb.json")

SYSTEM_PROMPT = """
你是“百骑谱”AI 助手，负责把历史名马知识、情绪陪伴和文创导购自然地结合起来。

回答要求：
1. 只依据提供的上下文回答，不要编造史实、人物、商品或来源。
2. 输出简体中文，语气温和、专业、自然，不要机械复述上下文。
3. 优先直接回应用户问题，再补充最相关的名马气质或故事价值。
4. 只有在商品和问题明显相关时，才自然地推荐 1 个商品。
5. 如果上下文不足，要明确说明信息有限，但仍给出下一步可追问方向。
6. 不要提及“RAG”“向量数据库”“开发者消息”“模板回答”等实现细节。
""".strip()

EMOTION_KEYWORDS = {
    "压力": "乌骓",
    "低谷": "乌骓",
    "迷茫": "的卢",
    "转机": "的卢",
    "机会": "的卢",
    "责任": "赤兔",
    "守护": "赤兔",
    "承诺": "赤兔",
    "坚持": "汗血",
    "长期": "汗血",
    "冷静": "绝影",
    "执行": "绝影",
}


def _tokenize(text: str) -> list[str]:
    if not text:
        return []

    tokens: list[str] = []
    lowered = text.lower()

    for token in re.findall(r"[a-z0-9]+", lowered):
        if token:
            tokens.append(token)

    for chunk in re.findall(r"[\u4e00-\u9fff]+", text):
        if not chunk:
            continue
        tokens.append(chunk)
        tokens.extend(list(chunk))
        tokens.extend(chunk[index : index + 2] for index in range(len(chunk) - 1))
        if len(chunk) >= 3:
            tokens.extend(chunk[index : index + 3] for index in range(len(chunk) - 2))

    return [token for token in tokens if token.strip()]


def _embed_text(text: str) -> dict[str, int]:
    return dict(Counter(_tokenize(text)))


def build_vectordb(docs: list[dict[str, Any]], out_path: str | None = None) -> str:
    resolved_out_path = out_path or VDB_PATH
    os.makedirs(os.path.dirname(resolved_out_path), exist_ok=True)

    entries = []
    for doc in docs:
        text = doc.get("text", "")
        entries.append(
            {
                "id": doc.get("id"),
                "text": text,
                "metadata": doc.get("metadata", {}),
                "embedding": _embed_text(text),
            }
        )

    with open(resolved_out_path, "w", encoding="utf-8") as file:
        json.dump(entries, file, ensure_ascii=False, indent=2)

    return resolved_out_path


def _cosine_sim(a: dict[str, int], b: dict[str, int]) -> float:
    if not a or not b:
        return 0.0

    common_keys = set(a.keys()) & set(b.keys())
    numerator = sum(a[key] * b[key] for key in common_keys)
    denominator = math.sqrt(sum(value * value for value in a.values())) * math.sqrt(sum(value * value for value in b.values()))
    return numerator / denominator if denominator > 0 else 0.0


def _load_corpus(corpus_path: str | None = None) -> list[dict[str, Any]]:
    resolved_path = corpus_path or CORPUS_PATH
    if not os.path.exists(resolved_path):
        return []

    with open(resolved_path, "r", encoding="utf-8") as file:
        return json.load(file)


def ensure_vectordb(corpus_path: str | None = None, db_path: str | None = None) -> str | None:
    resolved_db_path = db_path or VDB_PATH
    resolved_corpus_path = corpus_path or CORPUS_PATH

    if os.path.exists(resolved_db_path):
        return resolved_db_path

    docs = _load_corpus(resolved_corpus_path)
    if not docs:
        return None

    return build_vectordb(docs, resolved_db_path)


def query_vectordb(query: str, top_k: int = 5, db_path: str | None = None, corpus_path: str | None = None) -> list[dict[str, Any]]:
    resolved_db_path = db_path or VDB_PATH
    if not os.path.exists(resolved_db_path):
        built_path = ensure_vectordb(corpus_path=corpus_path, db_path=resolved_db_path)
        if not built_path:
            return []

    with open(resolved_db_path, "r", encoding="utf-8") as file:
        entries = json.load(file)

    query_embedding = _embed_text(query)
    scored_entries = []
    for entry in entries:
        score = _cosine_sim(query_embedding, entry.get("embedding", {}))
        if score > 0:
            scored_entries.append((score, entry))

    scored_entries.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "score": score,
            "id": entry.get("id"),
            "text": entry.get("text", ""),
            "metadata": entry.get("metadata", {}),
        }
        for score, entry in scored_entries[:top_k]
    ]


def get_rag_status() -> dict[str, Any]:
    docs = _load_corpus()
    vectordb_path = ensure_vectordb()
    vector_entries = []
    if vectordb_path and os.path.exists(vectordb_path):
        try:
            with open(vectordb_path, "r", encoding="utf-8") as file:
                vector_entries = json.load(file)
        except (json.JSONDecodeError, OSError):
            vector_entries = []

    horse_names = []
    for doc in docs:
        name = str(doc.get("metadata", {}).get("name", "")).strip()
        if name and name not in horse_names:
            horse_names.append(name)

    return {
        "status": "ready" if docs and vector_entries else "building" if docs else "missing",
        "corpus_path": CORPUS_PATH,
        "vectordb_path": vectordb_path,
        "document_count": len(docs),
        "vector_count": len(vector_entries),
        "unique_horse_count": len(horse_names),
        "sample_horses": horse_names[:8],
        "top_k": get_settings().RAG_TOP_K,
    }


def _shorten(text: str, limit: int = 68) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3]}..."


def _normalize_messages(messages_or_text: str | list[dict[str, Any]] | None) -> list[dict[str, str]]:
    if isinstance(messages_or_text, str):
        text = messages_or_text.strip() or "你好"
        return [{"role": "user", "content": text}]

    normalized: list[dict[str, str]] = []
    for message in messages_or_text or []:
        role = str(message.get("role", "")).strip().lower()
        content = str(message.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue
        normalized.append({"role": role, "content": content})

    if not normalized:
        normalized.append({"role": "user", "content": "你好"})

    return normalized


def _latest_user_message(messages: list[dict[str, str]]) -> str:
    for message in reversed(messages):
        if message["role"] == "user":
            return message["content"]
    return "你好"


def _build_search_query(messages: list[dict[str, str]], user_window: int = 3) -> str:
    user_messages = [message["content"] for message in messages if message["role"] == "user"]
    if not user_messages:
        return "你好"
    return "\n".join(user_messages[-user_window:])


def _detect_horse_name(search_text: str, horses: list[Horse], hits: list[dict[str, Any]]) -> str | None:
    lowered = search_text.lower()

    for horse in horses:
        if horse.name in search_text or horse.id in lowered:
            return horse.name

    for keyword, horse_name in EMOTION_KEYWORDS.items():
        if keyword in search_text:
            return horse_name

    for hit in hits:
        metadata = hit.get("metadata", {})
        horse_name = metadata.get("name")
        if horse_name:
            return horse_name

    return None


def _match_horse(search_text: str, horses: list[Horse], hits: list[dict[str, Any]]) -> Horse | None:
    detected_name = _detect_horse_name(search_text, horses, hits)
    if detected_name:
        for horse in horses:
            if horse.name == detected_name or horse.id == detected_name:
                return horse

    query_embedding = _embed_text(search_text)
    best_horse = None
    best_score = 0.0
    for horse in horses:
        searchable_text = " ".join(
            filter(
                None,
                [
                    horse.name,
                    horse.title,
                    horse.trait,
                    horse.story,
                    horse.full_story,
                    horse.historical_source,
                    horse.dynasty,
                    horse.owner,
                    " ".join(horse.traits or []),
                ],
            )
        )
        score = _cosine_sim(query_embedding, _embed_text(searchable_text))
        if score > best_score:
            best_score = score
            best_horse = horse

    return best_horse if best_score > 0 else None


def _build_sources(hits: list[dict[str, Any]], horse: Horse | None) -> list[dict[str, str]]:
    sources = []
    seen_keys = set()

    for hit in hits:
        metadata = hit.get("metadata", {})
        source_name = metadata.get("source") or "知识库"
        horse_name = metadata.get("name") or (horse.name if horse else hit.get("id", ""))
        source_key = f"{horse_name}:{source_name}:{hit.get('id')}"
        if source_key in seen_keys:
            continue

        seen_keys.add(source_key)
        sources.append(
            {
                "title": " · ".join(part for part in [horse_name, source_name] if part),
                "horse_name": horse_name or "",
                "snippet": _shorten(hit.get("text", "")),
                "source": source_name,
            }
        )

    if not sources and horse:
        sources.append(
            {
                "title": " · ".join(part for part in [horse.name, horse.historical_source or "历史资料"] if part),
                "horse_name": horse.name,
                "snippet": _shorten(horse.full_story or horse.story),
                "source": horse.historical_source or "历史资料",
            }
        )

    return sources[:3]


def _find_recommended_product(db: Session, horse: Horse | None) -> dict[str, Any] | None:
    if not horse:
        return None

    product = db.query(Product).filter(Product.horse_id == horse.id).order_by(Product.price.asc()).first()
    if not product:
        return None

    return {
        "id": product.id,
        "horse_id": product.horse_id,
        "name": product.name,
        "price": product.price,
    }


def _compose_general_answer(user_msg: str, hits: list[dict[str, Any]]) -> str:
    if hits:
        top_hits = "、".join(hit.get("metadata", {}).get("name", hit.get("id", "资料")) for hit in hits[:2])
        return (
            f"我先从知识库里找到了和你问题最接近的内容，重点集中在 {top_hits}。"
            "如果你愿意，我可以继续帮你拆解某匹名马的故事、精神标签，"
            "或者按你现在的状态给你匹配一匹更适合你的守护名马。"
        )

    return (
        f"我收到你的问题了：“{user_msg}”。"
        "当前知识库里还没有特别直接的命中，但我可以从名马故事、情绪匹配或相关藏品推荐三个方向继续帮你展开。"
    )


def _compose_horse_answer(user_msg: str, horse: Horse, hits: list[dict[str, Any]], product: dict[str, Any] | None) -> str:
    recommend_intent = any(keyword in user_msg for keyword in ["推荐", "适合", "压力", "低谷", "匹配", "守护", "送礼", "送人", "选择"])
    story_intent = any(keyword in user_msg for keyword in ["故事", "怎么", "历史", "出处", "谁", "资料"])

    summary = horse.full_story or horse.story
    if hits:
        summary = hits[0].get("text") or summary

    parts: list[str] = []
    if recommend_intent:
        parts.append(f"按你刚才的描述，我会优先想到 {horse.name}（{horse.title}）。")
    elif story_intent:
        parts.append(f"你提到的 {horse.name}，我先帮你把和它最相关的故事线整理一下。")
    else:
        parts.append(f"结合当前知识库内容，我第一时间想到的是 {horse.name}（{horse.title}）。")

    parts.append(summary)
    parts.append(f"{horse.name}最核心的气质是“{horse.trait}”，当前稀有度为 {horse.rarity}。")

    if product and recommend_intent:
        parts.append(f"如果你想继续了解或拿来送礼，也可以看看 {product['name']}，当前价格是 ¥{product['price']}。")

    parts.append("如果你愿意，我还可以继续帮你比较它和其他名马的区别，或者按你的处境再细化一次推荐。")
    return "\n\n".join(parts)


def _build_context_block(
    latest_user_msg: str,
    hits: list[dict[str, Any]],
    horse: Horse | None,
    product: dict[str, Any] | None,
    personality_match: dict[str, Any] | None,
    recommendation_strategy: dict[str, Any] | None,
) -> str:
    sections = [f"用户最新问题：{latest_user_msg}"]

    if horse:
        sections.append(
            "\n".join(
                [
                    "候选名马：",
                    f"- 名称：{horse.name}",
                    f"- 标题：{horse.title}",
                    f"- 气质：{horse.trait}",
                    f"- 稀有度：{horse.rarity}",
                    f"- 主人：{horse.owner or '未知'}",
                    f"- 朝代：{horse.dynasty or '未知'}",
                    f"- 故事摘要：{horse.full_story or horse.story}",
                ]
            )
        )

    if hits:
        source_lines = ["知识库命中片段："]
        for index, hit in enumerate(hits, start=1):
            metadata = hit.get("metadata", {})
            source_lines.extend(
                [
                    f"{index}. 名称：{metadata.get('name') or hit.get('id', '未知')}",
                    f"   来源：{metadata.get('source') or '知识库'}",
                    f"   内容：{hit.get('text', '')}",
                ]
            )
        sections.append("\n".join(source_lines))
    else:
        sections.append("知识库命中片段：暂无直接命中，请基于现有上下文谨慎回答。")

    if product:
        sections.append(
            "\n".join(
                [
                    "可推荐商品：",
                    f"- 商品名：{product['name']}",
                    f"- horse_id：{product['horse_id']}",
                    f"- 价格：¥{product['price']}",
                ]
            )
        )

    if personality_match:
        sections.append(
            "\n".join(
                [
                    "性格匹配分析：",
                    f"- 标签：{personality_match.get('label')}",
                    f"- 匹配名马：{personality_match.get('horse_name')}",
                    f"- 信号：{'、'.join(personality_match.get('signals', []))}",
                    f"- 解释：{personality_match.get('summary')}",
                ]
            )
        )

    if recommendation_strategy:
        sections.append(
            "\n".join(
                [
                    "用户分层推荐策略：",
                    f"- 用户层级：{recommendation_strategy.get('tier_label')}",
                    f"- 标题：{recommendation_strategy.get('title')}",
                    f"- 建议：{recommendation_strategy.get('guidance')}",
                    f"- 下一步：{recommendation_strategy.get('next_action')}",
                ]
            )
        )

    return "\n\n".join(sections)


def _serialize_recent_messages(messages: list[dict[str, str]], limit: int = 8) -> list[dict[str, str]]:
    return [{"role": message["role"], "content": message["content"]} for message in messages[-limit:]]


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


def _generate_openai_reply(
    messages: list[dict[str, str]],
    latest_user_msg: str,
    hits: list[dict[str, Any]],
    horse: Horse | None,
    product: dict[str, Any] | None,
    personality_match: dict[str, Any] | None,
    recommendation_strategy: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        return None, None

    context_prompt = (
        "请严格依据下面的项目上下文和聊天历史回答用户。"
        "如果历史消息里存在代词指代，请结合上下文理解指代对象。"
        "如果上下文不足，不要编造。"
        f"\n\n{_build_context_block(latest_user_msg, hits, horse, product, personality_match, recommendation_strategy)}"
    )

    payload: dict[str, Any] = {
        "model": settings.OPENAI_MODEL,
        "instructions": SYSTEM_PROMPT,
        "input": [{"role": "developer", "content": context_prompt}, *_serialize_recent_messages(messages)],
        "max_output_tokens": settings.OPENAI_MAX_OUTPUT_TOKENS,
    }
    if settings.OPENAI_REASONING_EFFORT:
        payload["reasoning"] = {"effort": settings.OPENAI_REASONING_EFFORT}

    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "X-Client-Request-Id": str(uuid.uuid4()),
    }
    endpoint = f"{settings.OPENAI_BASE_URL.rstrip('/')}/responses"

    try:
        response = httpx.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=settings.OPENAI_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return None, None

    reply_text = _extract_response_text(response.json())
    if not reply_text:
        return None, None

    return reply_text, settings.OPENAI_MODEL


def generate_chat_reply(messages_or_text: str | list[dict[str, Any]], db: Session, user: User | None = None) -> dict[str, Any]:
    settings = get_settings()
    messages = _normalize_messages(messages_or_text)
    latest_user_msg = _latest_user_message(messages)
    search_query = _build_search_query(messages)
    hits = query_vectordb(search_query, top_k=settings.RAG_TOP_K)

    horses = db.query(Horse).all()
    matched_horse = _match_horse(search_query, horses, hits) if horses else None
    recommended_product = _find_recommended_product(db, matched_horse)
    collection_count = db.query(Collection).filter(Collection.user_id == user.id).count() if user else 0
    personality_match = assess_personality_context(latest_user_msg, matched_horse=matched_horse, hits=hits)
    recommendation_strategy = build_recommendation_strategy(
        user=user,
        matched_horse=matched_horse,
        recommended_product=recommended_product,
        personality_match=personality_match,
        collection_count=collection_count,
    )
    sources = _build_sources(hits, matched_horse)

    llm_message, model_name = _generate_openai_reply(
        messages=messages,
        latest_user_msg=latest_user_msg,
        hits=hits,
        horse=matched_horse,
        product=recommended_product,
        personality_match=personality_match,
        recommendation_strategy=recommendation_strategy,
    )

    if llm_message:
        message = llm_message
        generation_mode = "llm"
    elif matched_horse:
        message = _compose_horse_answer(latest_user_msg, matched_horse, hits, recommended_product)
        generation_mode = "fallback"
    else:
        message = _compose_general_answer(latest_user_msg, hits)
        generation_mode = "fallback"

    return {
        "message": message,
        "sources": sources,
        "matched_horse": (
            {
                "id": matched_horse.id,
                "name": matched_horse.name,
                "title": matched_horse.title,
            }
            if matched_horse
            else None
        ),
        "recommended_product": recommended_product,
        "personality_match": personality_match,
        "recommendation_strategy": recommendation_strategy,
        "generation_mode": generation_mode,
        "model": model_name,
    }
