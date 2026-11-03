from __future__ import annotations

from typing import Any

from app.models.product import Product
from app.services.localize import convert_price_from_cny

AMAZON_MARKETS: dict[str, dict[str, Any]] = {
    "amazon_us": {
        "marketplace": "Amazon US",
        "locale": "en",
        "currency": "USD",
        "markup": 1.15,
        "domain": "https://www.amazon.com",
    },
    "amazon_jp": {
        "marketplace": "Amazon Japan",
        "locale": "ja",
        "currency": "JPY",
        "markup": 1.15,
        "domain": "https://www.amazon.co.jp",
    },
}


def supports_platform(platform: str) -> bool:
    return platform in AMAZON_MARKETS


def platform_locale(platform: str) -> str:
    return str(AMAZON_MARKETS[platform]["locale"])


def publish_listing(product: Product, translation: dict[str, Any], platform: str) -> dict[str, Any]:
    market = AMAZON_MARKETS[platform]
    base_price = float(translation.get("price") or convert_price_from_cny(float(product.price), market["currency"]))
    final_price = round(base_price * float(market["markup"]), 2)
    original_title = str(translation["title"])
    title = original_title[:180]
    warnings: list[str] = []
    if len(original_title) > 180:
        warnings.append("标题已裁剪到 Amazon 建议长度 180 字符。")
    return {
        "platform": platform,
        "marketplace": market["marketplace"],
        "status": "prepared",
        "locale": market["locale"],
        "currency": market["currency"],
        "price": final_price,
        "listing_id": f"amz_{platform.split('_')[-1]}_{product.id}",
        "title": title,
        "highlights": list(translation.get("highlights") or [])[:5],
        "marketplace_url": f"{market['domain']}/dp/{product.id.upper()}",
        "warnings": warnings,
    }


def sync_inventory(platform: str, stock: int) -> dict[str, Any]:
    market = AMAZON_MARKETS[platform]
    return {
        "platform": platform,
        "status": "synced",
        "stock": stock,
        "currency": market["currency"],
        "message": f"{market['marketplace']} 可售库存已更新为 {stock}",
    }
