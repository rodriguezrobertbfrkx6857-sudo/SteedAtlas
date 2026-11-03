"""Optional catalogue/personality/product interaction, never a source of evidence."""

import re

from app.models.horse import Horse
from app.models.product import Product
from app.services.personality import assess_personality_context
from app.services.recommend import build_recommendation_strategy


# Explicit requests for evidence take precedence over playful/shopping keywords.
# Include original-text and traditional-script forms; this is intent routing,
# not a claim that a source exists or that a statement is historically true.
_EVIDENCE_INTENT = re.compile(
    r"史[实實书書籍料]|出处|出處|原文|引文|引证|引證|文献|文獻|"
    r"记载|記載|证据|證據|考证|考證|真实性|真實性|是否真的|证明|證明"
)


def culture_reply(db, query, user=None):
    shopping = bool(re.search("商品|购买|周边|送礼|礼物|多少钱|预算|价格|购物", query))
    playful = bool(re.search("匹配|适合我|像哪匹|性格|心情|压力|迷茫|鼓励|陪我|聊聊|互动|讲故事|猜谜", query))
    if not shopping and not playful:
        return None
    # Factual questions remain in the evidence lane, even if they contain personality words.
    if _EVIDENCE_INTENT.search(query):
        return None
    horses = db.query(Horse).all()
    horse = next((h for h in horses if h.name in query or h.id in query.lower()), None)
    personality = assess_personality_context(query, matched_horse=horse, hits=[])
    if not horse and personality:
        horse = next((h for h in horses if h.name == personality["horse_name"]), None)
    if not horse and playful and horses:
        horse = next((h for h in horses if h.name == "赤兔"), horses[0])
        personality = assess_personality_context(query, matched_horse=horse, hits=[])
    if not horse:
        return {
            "message": "可以先告诉我喜欢的名马、风格或预算，我会从现有图鉴和商品中帮你挑选。",
            "mode": "CULTURE",
            "culture_label": "EDITORIAL_INTERACTION",
        }
    product = None
    if shopping:
        candidates = (
            db.query(Product)
            .filter(Product.horse_id == horse.id, Product.stock > 0)
            .order_by(Product.price.asc())
            .all()
        )
        budget = re.search(r"(?:预算|不超过|以内)[约为是：: ]*(\d+(?:\.\d+)?)", query)
        if not budget:
            budget = re.search(r"(\d+(?:\.\d+)?)\s*元?(?:以内|以下)", query)
        cap = float(budget[1]) if budget else None
        p = next((p for p in candidates if cap is None or p.price <= cap), None)
        if p:
            product = {"id": p.id, "horse_id": p.horse_id, "name": p.name, "price": p.price, "stock": p.stock}
    strategy = build_recommendation_strategy(user, horse, product, personality)
    text = "文化互动／编辑整理：这是一种趣味联想，不是心理测评或历史证据。\n"
    text += (personality or {}).get("summary") or f"可以从{horse.name}的图鉴主题开始了解。"
    if "故事" in query:
        text += "\n编辑故事：" + (horse.story or "暂未收录故事。")
    if "猜谜" in query:
        text += f"\n来猜一猜：图鉴称号是“{horse.title}”，你猜是哪匹马？可以继续问它的出处。"
    if shopping:
        text += (
            f"\n现有商品：{product['name']}，标价 ¥{product['price']:g}。可到原站商城查看详情，自行决定是否购买。"
            if product
            else "\n当前没有找到这匹马符合预算且有库存的商品，可以调整条件或浏览商城。"
        )
    else:
        text += "\n你可以继续聊它的文化寓意，或问“有什么原文出处”来查文献。"
    return {
        "mode": "CULTURE",
        "message": text,
        "culture_label": "EDITORIAL_INTERACTION",
        "matched_horse": {"id": horse.id, "name": horse.name, "title": horse.title},
        "personality_match": personality,
        "recommended_product": product,
        "recommendation_strategy": strategy,
    }
