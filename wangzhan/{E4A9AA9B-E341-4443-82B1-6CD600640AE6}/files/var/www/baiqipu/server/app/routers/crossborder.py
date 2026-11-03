import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.crossborder_publish_record import CrossborderPublishRecord
from app.models.horse import Horse
from app.models.product import Product
from app.models.user import User
from app.schemas.crossborder import (
    CrossborderPublishOut,
    CrossborderPublishRecordDetailOut,
    CrossborderPublishRecordListOut,
    CrossborderPublishRecordOut,
    CrossborderPlatformStatusOut,
    CrossborderPlatformStatusResponseOut,
    CrossborderPlatformStatusSummaryOut,
    CrossborderShopeeAuthUrlOut,
    CrossborderShopeePublishConfigListOut,
    CrossborderShopeePublishConfigOut,
    CrossborderShopeeConnectionListOut,
    CrossborderShopeeConnectionOut,
    CrossborderShopeeConnectionSummaryOut,
    CrossborderShopeeRefreshRequest,
    CrossborderShopeeShopInfoOut,
    CrossborderShopeeTokenExchangeOut,
    CrossborderShopeeTokenExchangeRequest,
    CrossborderPublishRequest,
    CrossborderSyncInventoryOut,
    CrossborderSyncInventoryRequest,
    CrossborderTranslateOut,
    CrossborderTranslateRequest,
)
from app.services import amazon, localize, shopee
from app.services.auth import get_current_staff_user

router = APIRouter(prefix="/crossborder", tags=["cross-border"])
settings = get_settings()

SHIPPING_ZONES = {
    "domestic": {"name": "中国大陆", "fee": 0, "days": "3-5"},
    "hk_mo_tw": {"name": "港澳台", "fee": 30, "days": "5-7"},
    "asia": {"name": "亚洲", "fee": 60, "days": "7-14"},
    "us_eu": {"name": "欧美", "fee": 120, "days": "10-20"},
    "other": {"name": "其他地区", "fee": 150, "days": "14-30"},
}

I18N_LABELS = {
    "zh-CN": {"add_to_cart": "加入购物车", "buy_now": "立即购买", "currency": "¥"},
    "en": {"add_to_cart": "Add to Cart", "buy_now": "Buy Now", "currency": "$"},
    "ja": {"add_to_cart": "カートに入れる", "buy_now": "今すぐ購入", "currency": "¥"},
    "ko": {"add_to_cart": "장바구니에 추가", "buy_now": "바로 구매", "currency": "₩"},
}


class ExchangeRateOut(BaseModel):
    base: str
    rates: dict[str, float]


class ShippingEstimate(BaseModel):
    zone: str
    zone_name: str
    fee: float
    fee_converted: float
    currency: str
    delivery_days: str


class I18nLabels(BaseModel):
    locale: str
    labels: dict[str, str]


ETSY_MARKET = {
    "marketplace": "Etsy Global",
    "locale": "en",
    "currency": "USD",
    "markup": 1.18,
    "domain": "https://www.etsy.com/listing",
}

LIVE_PREVIEW_WARNING = "Live publish is currently wired only for Shopee; this platform returned a prepared payload instead."

PLATFORM_CREDENTIALS = {
    "shopee_my": {
        "marketplace": "Shopee Malaysia",
        "envs": ["SHOPEE_PARTNER_ID", "SHOPEE_PARTNER_KEY", "SHOPEE_SHOP_ID_MY", "SHOPEE_REDIRECT_URL"],
    },
    "shopee_th": {
        "marketplace": "Shopee Thailand",
        "envs": ["SHOPEE_PARTNER_ID", "SHOPEE_PARTNER_KEY", "SHOPEE_SHOP_ID_TH", "SHOPEE_REDIRECT_URL"],
    },
    "amazon_us": {
        "marketplace": "Amazon US",
        "envs": ["AMAZON_SELLER_ID", "AMAZON_LWA_CLIENT_ID", "AMAZON_LWA_CLIENT_SECRET", "AMAZON_MARKETPLACE_ID_US"],
    },
    "amazon_jp": {
        "marketplace": "Amazon Japan",
        "envs": ["AMAZON_SELLER_ID", "AMAZON_LWA_CLIENT_ID", "AMAZON_LWA_CLIENT_SECRET", "AMAZON_MARKETPLACE_ID_JP"],
    },
    "etsy_global": {
        "marketplace": "Etsy Global",
        "envs": ["ETSY_API_KEY", "ETSY_SHOP_ID"],
    },
}


def _get_product_and_horse(db: Session, product_id: str) -> tuple[Product, Horse]:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    horse = db.query(Horse).filter(Horse.id == product.horse_id).first()
    if not horse:
        raise HTTPException(status_code=404, detail="Related horse not found")

    return product, horse


def _normalize_unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def _publish_to_etsy(product: Product, translation: dict, platform: str) -> dict:
    base_price = float(translation.get("price") or localize.convert_price_from_cny(float(product.price), "USD"))
    final_price = round(base_price * float(ETSY_MARKET["markup"]), 2)
    original_title = str(translation["title"])
    title = original_title[:140]
    warnings: list[str] = []
    if len(original_title) > 140:
        warnings.append("标题已裁剪到 Etsy 建议长度 140 字符。")
    return {
        "platform": platform,
        "marketplace": ETSY_MARKET["marketplace"],
        "status": "prepared",
        "locale": ETSY_MARKET["locale"],
        "currency": ETSY_MARKET["currency"],
        "price": final_price,
        "listing_id": f"ets_{product.id}",
        "title": title,
        "highlights": list(translation.get("highlights") or [])[:5],
        "marketplace_url": f"{ETSY_MARKET['domain']}/{product.id}",
        "warnings": warnings,
    }


def _sync_to_etsy(stock: int) -> dict:
    return {
        "platform": "etsy_global",
        "status": "synced",
        "stock": stock,
        "currency": ETSY_MARKET["currency"],
        "message": f"{ETSY_MARKET['marketplace']} 可售库存已更新为 {stock}",
    }


def _resolve_platform_locale(platform: str) -> str:
    if shopee.supports_platform(platform):
        return shopee.platform_locale(platform)
    if amazon.supports_platform(platform):
        return amazon.platform_locale(platform)
    if platform == "etsy_global":
        return str(ETSY_MARKET["locale"])
    raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")


def _build_platform_status(platform: str) -> CrossborderPlatformStatusOut:
    config = PLATFORM_CREDENTIALS[platform]
    missing_envs = [name for name in config["envs"] if not str(getattr(settings, name, "") or "").strip()]
    configured = len(missing_envs) == 0
    return CrossborderPlatformStatusOut(
        platform=platform,
        marketplace=str(config["marketplace"]),
        configured=configured,
        mode="ready" if configured else "missing_credentials",
        missing_envs=missing_envs,
        note=(
            f"{config['marketplace']} 已具备真实凭据，可继续接平台 API。"
            if configured
            else f"{config['marketplace']} 仍缺少 {len(missing_envs)} 项环境变量。"
        ),
    )


def _serialize_publish_record(record: CrossborderPublishRecord) -> CrossborderPublishRecordOut:
    return CrossborderPublishRecordOut(
        id=record.id,
        product_id=record.product_id,
        platform=record.platform,
        marketplace=record.marketplace,
        mode=record.mode,
        status=record.status,
        locale=record.locale,
        currency=record.currency,
        shop_id=record.shop_id,
        listing_id=record.listing_id,
        title=record.title,
        price=record.price,
        marketplace_url=record.marketplace_url,
        request_path=record.request_path,
        request_id=record.request_id,
        error_message=record.error_message,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _serialize_publish_record_detail(record: CrossborderPublishRecord) -> CrossborderPublishRecordDetailOut:
    base = _serialize_publish_record(record)
    return CrossborderPublishRecordDetailOut(
        **base.model_dump(),
        warnings=list(record.warnings or []),
        request_payload=dict(record.request_payload or {}),
        response_payload=dict(record.response_payload or {}),
    )


def _get_publish_record(db: Session, record_id: str) -> CrossborderPublishRecord:
    record = db.query(CrossborderPublishRecord).filter(CrossborderPublishRecord.id == record_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Publish record not found")
    return record


def _resolve_publish_translation(
    *,
    product: Product,
    horse: Horse,
    platform: str,
    preferred_locale: str | None = None,
) -> dict:
    locale = preferred_locale or _resolve_platform_locale(platform)
    cached = dict(product.translations or {}).get(locale)
    if isinstance(cached, dict):
        return cached
    return localize.localize_product(product, horse, locale)


def _create_publish_record(
    *,
    product: Product,
    platform: str,
    result: dict[str, object],
    user_id: str,
) -> CrossborderPublishRecord:
    return CrossborderPublishRecord(
        id=f"xrec_{uuid.uuid4().hex[:12]}",
        product_id=product.id,
        platform=platform,
        marketplace=str(result.get("marketplace") or platform),
        mode=str(result.get("mode") or "preview"),
        status=str(result.get("status") or "prepared"),
        locale=str(result.get("locale") or ""),
        currency=str(result.get("currency") or ""),
        shop_id=result.get("shop_id"),
        listing_id=str(result["listing_id"]) if result.get("listing_id") is not None else None,
        title=str(result.get("title") or ""),
        price=float(result["price"]) if result.get("price") is not None else None,
        marketplace_url=str(result["marketplace_url"]) if result.get("marketplace_url") else None,
        warnings=list(result.get("warnings") or []),
        request_path=str(result["request_path"]) if result.get("request_path") else None,
        request_id=str(result["request_id"]) if result.get("request_id") else None,
        request_payload=dict(result.get("request_payload") or {}),
        response_payload=dict(result.get("raw") or {}),
        error_message=str(result["error"]) if result.get("error") else None,
        published_by_user_id=user_id,
    )


def _build_failed_publish_result(
    *,
    platform: str,
    marketplace: str,
    locale: str,
    currency: str,
    price: float,
    title: str,
    highlights: list[str],
    warnings: list[str],
    mode: str,
    error: str,
    shop_id: int | None = None,
    request_path: str | None = None,
) -> dict[str, object]:
    return {
        "platform": platform,
        "marketplace": marketplace,
        "status": "failed",
        "mode": mode,
        "locale": locale,
        "currency": currency,
        "price": price,
        "listing_id": None,
        "title": title,
        "highlights": highlights,
        "marketplace_url": None,
        "warnings": warnings,
        "shop_id": shop_id,
        "request_path": request_path,
        "error": error,
    }


def _publish_to_platform(
    *,
    db: Session,
    user: User,
    product: Product,
    translation: dict,
    platform: str,
    mode: str,
    shop_id: int | None = None,
) -> dict[str, object]:
    target_locale = _resolve_platform_locale(platform)
    marketplace = ""
    locale = str(translation.get("locale") or target_locale)
    currency = str(translation.get("currency") or "")
    price = float(translation.get("price") or 0)
    title = str(translation.get("title") or product.name)
    highlights = list(translation.get("highlights") or [])[:3]
    warnings: list[str] = []
    request_path = None

    try:
        if shopee.supports_platform(platform):
            marketplace = shopee.get_platform_marketplace(platform)
            if mode == "live":
                request_path = shopee.LIVE_ADD_ITEM_PATH
                result = shopee.publish_listing_live(
                    db,
                    product=product,
                    translation=translation,
                    platform=platform,
                    shop_id=shop_id,
                    connected_by_user_id=user.id,
                )
            else:
                result = shopee.publish_listing(product, translation, platform)
                result["mode"] = "preview"
                result["shop_id"] = shop_id or result.get("shop_id")
                try:
                    publish_config = shopee.resolve_publish_config(db, platform)
                    result["request_payload"] = shopee.build_listing_payload(
                        product,
                        translation,
                        platform,
                        publish_config=publish_config,
                    )["payload"]
                except ValueError:
                    result["request_payload"] = {}
        elif amazon.supports_platform(platform):
            marketplace = amazon.AMAZON_MARKETS[platform]["marketplace"]
            result = amazon.publish_listing(product, translation, platform)
            result["mode"] = "preview"
            if mode == "live":
                result["warnings"] = [*list(result.get("warnings") or []), LIVE_PREVIEW_WARNING]
        elif platform == "etsy_global":
            marketplace = ETSY_MARKET["marketplace"]
            result = _publish_to_etsy(product, translation, platform)
            result["mode"] = "preview"
            if mode == "live":
                result["warnings"] = [*list(result.get("warnings") or []), LIVE_PREVIEW_WARNING]
        else:
            raise ValueError(f"Unsupported platform: {platform}")
    except ValueError as exc:
        result = _build_failed_publish_result(
            platform=platform,
            marketplace=marketplace or platform,
            locale=locale,
            currency=currency,
            price=price,
            title=title,
            highlights=highlights,
            warnings=warnings,
            mode=mode,
            shop_id=shop_id,
            request_path=request_path,
            error=str(exc),
        )
    except httpx.HTTPError as exc:
        result = _build_failed_publish_result(
            platform=platform,
            marketplace=marketplace or platform,
            locale=locale,
            currency=currency,
            price=price,
            title=title,
            highlights=highlights,
            warnings=warnings,
            mode=mode,
            shop_id=shop_id,
            request_path=request_path,
            error=f"Shopee request failed: {exc}",
        )
    except RuntimeError as exc:
        result = _build_failed_publish_result(
            platform=platform,
            marketplace=marketplace or platform,
            locale=locale,
            currency=currency,
            price=price,
            title=title,
            highlights=highlights,
            warnings=warnings,
            mode=mode,
            shop_id=shop_id,
            request_path=request_path,
            error=str(exc),
        )

    return result


@router.get("/exchange-rates", response_model=ExchangeRateOut)
def get_exchange_rates():
    return ExchangeRateOut(base="CNY", rates=localize.EXCHANGE_RATES)


@router.get("/convert-price")
def convert_price(
    price_cny: float = Query(..., gt=0),
    currency: str = Query("USD"),
):
    rate = localize.EXCHANGE_RATES.get(currency.upper())
    if not rate:
        raise HTTPException(status_code=400, detail=f"Unsupported currency: {currency}")
    return {
        "original": {"amount": price_cny, "currency": "CNY"},
        "converted": {"amount": localize.convert_price_from_cny(price_cny, currency.upper()), "currency": currency.upper()},
        "rate": rate,
    }


@router.get("/shipping-estimate", response_model=ShippingEstimate)
def estimate_shipping(
    zone: str = Query("domestic"),
    currency: str = Query("CNY"),
):
    zone_info = SHIPPING_ZONES.get(zone, SHIPPING_ZONES["other"])
    rate = localize.EXCHANGE_RATES.get(currency.upper(), 1.0)
    return ShippingEstimate(
        zone=zone,
        zone_name=zone_info["name"],
        fee=zone_info["fee"],
        fee_converted=round(float(zone_info["fee"]) * rate, 2),
        currency=currency.upper(),
        delivery_days=str(zone_info["days"]),
    )


@router.get("/i18n/{locale}", response_model=I18nLabels)
def get_i18n(locale: str = "zh-CN"):
    labels = I18N_LABELS.get(locale, I18N_LABELS["en"])
    return I18nLabels(locale=locale, labels=labels)


@router.get("/shipping-zones")
def list_zones():
    return [
        {"id": k, "name": v["name"], "fee_cny": v["fee"], "delivery_days": v["days"]}
        for k, v in SHIPPING_ZONES.items()
    ]


@router.get("/platform-status", response_model=CrossborderPlatformStatusResponseOut)
def get_platform_status(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_staff_user),
):
    platforms = {platform: _build_platform_status(platform) for platform in PLATFORM_CREDENTIALS}
    connection_map: dict[str, int] = {}
    for connection in shopee.list_connections(db):
        connection_map[connection.platform] = connection_map.get(connection.platform, 0) + 1
    for platform, count in connection_map.items():
        status_item = platforms.get(platform)
        if status_item:
            status_item.note = f"{status_item.note} 当前已保存 {count} 个店铺连接。"
    configured_count = sum(1 for item in platforms.values() if item.configured)
    return CrossborderPlatformStatusResponseOut(
        summary=CrossborderPlatformStatusSummaryOut(
            configured_count=configured_count,
            total_count=len(platforms),
        ),
        platforms=platforms,
    )


@router.get("/shopee/publish-configs", response_model=CrossborderShopeePublishConfigListOut)
def list_shopee_publish_configs(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_staff_user),
):
    connections = shopee.list_connections(db)
    items: list[CrossborderShopeePublishConfigOut] = []
    for platform in shopee.SHOPEE_MARKETS:
        config = shopee.resolve_publish_config(db, platform)
        shop_id = config.get("shop_id")
        matching_connection = next(
            (
                connection
                for connection in connections
                if connection.platform == platform and (shop_id is None or connection.shop_id == int(shop_id))
            ),
            None,
        )
        items.append(
            CrossborderShopeePublishConfigOut(
                platform=platform,
                marketplace=str(config.get("marketplace") or platform),
                shop_id=config.get("shop_id"),
                default_category_id=config.get("default_category_id"),
                default_logistic_id=config.get("default_logistic_id"),
                configured=bool(config.get("configured")),
                missing_fields=list(config.get("missing_fields") or []),
                live_ready=bool(config.get("live_ready")),
                live_issues=list(config.get("live_issues") or []),
                category_selection=dict(config.get("category_selection") or {}),
                logistic_selection=dict(config.get("logistic_selection") or {}),
                has_connected_shop=matching_connection is not None,
                connection_shop_id=matching_connection.shop_id if matching_connection else None,
            )
        )
    return CrossborderShopeePublishConfigListOut(total_count=len(items), items=items)


@router.post("/translate", response_model=CrossborderTranslateOut)
def translate_product(
    req: CrossborderTranslateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_staff_user),
):
    product, horse = _get_product_and_horse(db, req.product_id)
    languages = _normalize_unique(req.target_languages)
    if not languages:
        raise HTTPException(status_code=400, detail="target_languages is required")

    translations = localize.build_localized_bundle(product, horse, languages)
    if req.persist:
        merged_translations = dict(product.translations or {})
        merged_translations.update(translations)
        product.translations = merged_translations
        db.add(product)
        db.commit()
        db.refresh(product)

    return CrossborderTranslateOut(product_id=product.id, translations=translations)


@router.post("/publish", response_model=CrossborderPublishOut, status_code=status.HTTP_202_ACCEPTED)
def publish_product(
    req: CrossborderPublishRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_staff_user),
):
    product, horse = _get_product_and_horse(db, req.product_id)
    platforms = _normalize_unique(req.platforms)
    if not platforms:
        raise HTTPException(status_code=400, detail="platforms is required")

    translation_cache = dict(product.translations or {})
    results: dict[str, dict] = {}
    cache_updated = False

    for platform in platforms:
        target_locale = _resolve_platform_locale(platform)
        if req.use_localization:
            translation = translation_cache.get(target_locale)
            if not isinstance(translation, dict):
                translation = localize.localize_product(product, horse, target_locale)
                translation_cache[target_locale] = translation
                cache_updated = True
        else:
            translation = localize.localize_product(product, horse, "zh-CN")

        result = _publish_to_platform(
            db=db,
            user=user,
            product=product,
            translation=translation,
            platform=platform,
            mode=req.mode,
            shop_id=req.shop_id,
        )

        record = _create_publish_record(product=product, platform=platform, result=result, user_id=user.id)
        db.add(record)
        result["record_id"] = record.id
        results[platform] = result

    if cache_updated:
        product.translations = translation_cache
        db.add(product)
    db.commit()

    status_values = {str(item.get("status") or "") for item in results.values()}
    overall_status = "failed"
    if "submitted" in status_values:
        overall_status = "submitted"
    elif "prepared" in status_values:
        overall_status = "prepared"

    return CrossborderPublishOut(
        task_id=f"xpub_{uuid.uuid4().hex[:10]}",
        status=overall_status,
        mode=req.mode,
        platforms=results,
    )


@router.get("/publish-records", response_model=CrossborderPublishRecordListOut)
def list_publish_records(
    product_id: str | None = Query(None),
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_staff_user),
):
    query = db.query(CrossborderPublishRecord)
    if product_id:
        query = query.filter(CrossborderPublishRecord.product_id == product_id)

    total_count = query.count()
    items = (
        query.order_by(CrossborderPublishRecord.created_at.desc(), CrossborderPublishRecord.updated_at.desc())
        .limit(limit)
        .all()
    )
    return CrossborderPublishRecordListOut(
        product_id=product_id,
        total_count=total_count,
        items=[_serialize_publish_record(item) for item in items],
    )


@router.get("/publish-records/{record_id}", response_model=CrossborderPublishRecordDetailOut)
def get_publish_record_detail(
    record_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_staff_user),
):
    record = _get_publish_record(db, record_id)
    return _serialize_publish_record_detail(record)


@router.post("/publish-records/{record_id}/retry", response_model=CrossborderPublishOut, status_code=status.HTTP_202_ACCEPTED)
def retry_publish_record(
    record_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_staff_user),
):
    record = _get_publish_record(db, record_id)
    product, horse = _get_product_and_horse(db, record.product_id)
    translation = _resolve_publish_translation(
        product=product,
        horse=horse,
        platform=record.platform,
        preferred_locale=record.locale or None,
    )
    result = _publish_to_platform(
        db=db,
        user=user,
        product=product,
        translation=translation,
        platform=record.platform,
        mode=record.mode,
        shop_id=record.shop_id,
    )
    new_record = _create_publish_record(product=product, platform=record.platform, result=result, user_id=user.id)
    db.add(new_record)
    db.commit()
    result["record_id"] = new_record.id
    return CrossborderPublishOut(
        task_id=f"xpub_{uuid.uuid4().hex[:10]}",
        status=str(result.get("status") or "failed"),
        mode=record.mode,
        platforms={record.platform: result},
    )


@router.post("/publish-records/{record_id}/sync-status", response_model=CrossborderPublishRecordDetailOut)
def sync_publish_record_status(
    record_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_staff_user),
):
    record = _get_publish_record(db, record_id)
    if not shopee.supports_platform(record.platform):
        raise HTTPException(status_code=400, detail="Status sync is currently supported only for Shopee publish records")
    if not record.listing_id:
        raise HTTPException(status_code=400, detail="Publish record is missing listing_id")

    try:
        status_result = shopee.get_listing_status(
            db,
            platform=record.platform,
            item_id=record.listing_id,
            shop_id=record.shop_id,
            connected_by_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Shopee request failed: {exc}")
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    previous_payload = dict(record.response_payload or {})
    record.status = str(status_result.get("listing_status") or record.status)
    record.response_payload = {
        "publish": previous_payload,
        "status_sync": dict(status_result.get("raw") or {}),
    }
    record.request_id = str(status_result["raw"].get("request_id") or record.request_id or "")
    record.error_message = None
    db.add(record)
    db.commit()
    db.refresh(record)
    return _serialize_publish_record_detail(record)


@router.post("/sync-inventory", response_model=CrossborderSyncInventoryOut)
def sync_inventory(
    req: CrossborderSyncInventoryRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_staff_user),
):
    product, _ = _get_product_and_horse(db, req.product_id)
    stock_before = int(product.stock or 0)
    stock_after = stock_before + req.quantity_change
    if stock_after < 0:
        raise HTTPException(status_code=400, detail="Inventory cannot be negative")

    product.stock = stock_after
    db.add(product)
    db.commit()
    db.refresh(product)

    requested_platforms = _normalize_unique(req.platforms) or ["shopee_my", "amazon_us", "etsy_global"]
    synced: list[str] = []
    failed: list[str] = []
    platform_results: dict[str, dict] = {}

    for platform in requested_platforms:
        if shopee.supports_platform(platform):
            platform_results[platform] = shopee.sync_inventory(platform, stock_after)
            synced.append(platform)
        elif amazon.supports_platform(platform):
            platform_results[platform] = amazon.sync_inventory(platform, stock_after)
            synced.append(platform)
        elif platform == "etsy_global":
            platform_results[platform] = _sync_to_etsy(stock_after)
            synced.append(platform)
        else:
            failed.append(platform)

    return CrossborderSyncInventoryOut(
        product_id=product.id,
        stock_before=stock_before,
        stock_after=stock_after,
        synced=synced,
        failed=failed,
        platforms=platform_results,
    )


@router.get("/shopee/auth-url", response_model=CrossborderShopeeAuthUrlOut)
def get_shopee_auth_url(
    platform: str = Query("shopee_my"),
    _user: User = Depends(get_current_staff_user),
):
    try:
        return CrossborderShopeeAuthUrlOut(**shopee.build_auth_url(platform))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/shopee/token-exchange", response_model=CrossborderShopeeTokenExchangeOut)
def exchange_shopee_token(
    req: CrossborderShopeeTokenExchangeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_staff_user),
):
    try:
        payload = shopee.exchange_token(
            platform=req.platform,
            code=req.code,
            shop_id=req.shop_id,
        )
        connection = shopee.upsert_connection(
            db,
            platform=req.platform,
            token_payload=payload,
            connected_by_user_id=user.id,
        )
        payload["connection"] = shopee.serialize_connection(connection)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Shopee request failed: {exc}")
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return CrossborderShopeeTokenExchangeOut(**payload)


@router.get("/shopee/connections", response_model=CrossborderShopeeConnectionListOut)
def list_shopee_connections(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_staff_user),
):
    items = [CrossborderShopeeConnectionOut(**shopee.serialize_connection(item)) for item in shopee.list_connections(db)]
    expired_count = sum(1 for item in items if item.is_access_token_expired)
    return CrossborderShopeeConnectionListOut(
        summary=CrossborderShopeeConnectionSummaryOut(
            total_count=len(items),
            expired_count=expired_count,
            healthy_count=len(items) - expired_count,
        ),
        items=items,
    )


@router.post("/shopee/refresh-token", response_model=CrossborderShopeeTokenExchangeOut)
def refresh_shopee_token(
    req: CrossborderShopeeRefreshRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_staff_user),
):
    try:
        connection = shopee.get_connection(db, platform=req.platform, shop_id=req.shop_id)
        refresh_token = shopee.get_connection_refresh_token(connection)
        if not refresh_token:
            raise ValueError(f"{req.platform} / {connection.shop_id} is missing refresh_token")

        payload = shopee.refresh_access_token(
            platform=req.platform,
            refresh_token=refresh_token,
            shop_id=connection.shop_id,
        )
        refreshed = shopee.upsert_connection(
            db,
            platform=req.platform,
            token_payload=payload,
            connected_by_user_id=user.id,
        )
        payload["connection"] = shopee.serialize_connection(refreshed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Shopee request failed: {exc}")
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return CrossborderShopeeTokenExchangeOut(**payload)


@router.get("/shopee/shop-info", response_model=CrossborderShopeeShopInfoOut)
def get_shopee_shop_info(
    platform: str = Query("shopee_my"),
    shop_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_staff_user),
):
    try:
        payload = shopee.get_shop_info(
            db,
            platform=platform,
            shop_id=shop_id,
            connected_by_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Shopee request failed: {exc}")
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return CrossborderShopeeShopInfoOut(**payload)
