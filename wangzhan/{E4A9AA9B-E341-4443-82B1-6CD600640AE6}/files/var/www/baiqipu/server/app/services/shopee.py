from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.shopee_connection import ShopeeConnection
from app.models.product import Product
from app.models.shopee_publish_config import ShopeePublishConfig
from app.services.localize import convert_price_from_cny
from app.services.secrets import decrypt_text, encrypt_text

SHOPEE_MARKETS: dict[str, dict[str, Any]] = {
    "shopee_my": {
        "marketplace": "Shopee Malaysia",
        "locale": "ms",
        "currency": "MYR",
        "markup": 1.08,
        "domain": "https://shopee.com.my",
    },
    "shopee_th": {
        "marketplace": "Shopee Thailand",
        "locale": "th",
        "currency": "THB",
        "markup": 1.08,
        "domain": "https://shopee.co.th",
    },
    "shopee_sg": {
        "marketplace": "Shopee Singapore",
        "locale": "en",
        "currency": "USD",
        "markup": 1.08,
        "domain": "https://shopee.sg",
    },
}

ACCESS_TOKEN_DEFAULT_SECONDS = 4 * 60 * 60
REFRESH_TOKEN_DEFAULT_DAYS = 30
REFRESH_GRACE_SECONDS = 10 * 60
# Inference from Shopee Open Platform V2 naming conventions; verify the exact create-item path/fields
# against your partner app's current official docs before production rollout.
LIVE_ADD_ITEM_PATH = "/api/v2/product/add_item"
# Inference from Shopee Open Platform V2 naming conventions; verify the exact category path/params
# against your partner app's current official docs before production rollout.
CATEGORY_LIST_PATH = "/api/v2/product/get_category"
# Inference from Shopee Open Platform V2 naming conventions; verify the exact media upload path/fields
# against your partner app's current official docs before production rollout.
MEDIA_UPLOAD_IMAGE_PATH = "/api/v2/media_space/upload_image"
# Inference from Shopee Open Platform V2 naming conventions; verify the exact logistics path/params
# against your partner app's current official docs before production rollout.
LOGISTIC_CHANNEL_LIST_PATH = "/api/v2/logistics/get_channel_list"
# Inference from Shopee Open Platform V2 naming conventions; verify the exact read path/fields
# against your partner app's current official docs before production rollout.
ITEM_BASE_INFO_PATH = "/api/v2/product/get_item_base_info"

SHOPEE_ERROR_HINTS = {
    "error_param": "Shopee rejected one or more product fields. Check category, logistics, weight, and price.",
    "error_auth": "Shopee authorization is invalid or expired. Reconnect the shop or refresh the token.",
    "invalid access_token": "Shopee access token is invalid or expired. Reconnect the shop or refresh the token.",
    "item_name": "Shopee item name failed validation. Shorten the title and remove unsupported symbols.",
    "category_id": "Shopee category is missing or invalid. Update the platform configuration with a valid category id.",
    "logistic": "Shopee logistics configuration is invalid. Update the default logistic id for this marketplace.",
    "image": "Shopee image upload failed or the image payload is invalid. Recheck the source image URL and format.",
}

OPTION_CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "shopee_option_catalog.json"


def supports_platform(platform: str) -> bool:
    return platform in SHOPEE_MARKETS


def platform_locale(platform: str) -> str:
    return str(SHOPEE_MARKETS[platform]["locale"])


def get_platform_marketplace(platform: str) -> str:
    return str(SHOPEE_MARKETS[platform]["marketplace"])


def get_platform_shop_id(platform: str) -> int | None:
    settings = get_settings()
    env_map = {
        "shopee_my": settings.SHOPEE_SHOP_ID_MY,
        "shopee_th": settings.SHOPEE_SHOP_ID_TH,
    }
    raw_value = str(env_map.get(platform, "") or "").strip()
    if not raw_value:
        return None
    try:
        return int(raw_value)
    except ValueError:
        return None


def _normalize_item_status(value: str | None) -> str:
    normalized = str(value or "UNLIST").strip().upper()
    if normalized in {"NORMAL", "UNLIST"}:
        return normalized
    return "UNLIST"


def _default_publish_config(platform: str) -> dict[str, Any]:
    settings = get_settings()
    return {
        "platform": platform,
        "marketplace": get_platform_marketplace(platform),
        "shop_id": get_platform_shop_id(platform),
        "default_category_id": _as_int(str(getattr(settings, "SHOPEE_DEFAULT_CATEGORY_ID", "") or "").strip()),
        "default_logistic_id": _as_int(str(getattr(settings, "SHOPEE_DEFAULT_LOGISTIC_ID", "") or "").strip()),
        "category_options": [],
        "logistic_options": [],
        "default_weight_kg": float(getattr(settings, "SHOPEE_DEFAULT_WEIGHT_KG", 0.35) or 0.35),
        "item_status": _normalize_item_status(getattr(settings, "SHOPEE_LIVE_ITEM_STATUS", "UNLIST")),
        "upload_images": True,
        "notes": "",
        "source": "env_fallback",
        "updated_by_user_id": None,
        "created_at": None,
        "updated_at": None,
    }


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _token_preview(token: str | None) -> str | None:
    if not token:
        return None
    if len(token) <= 12:
        return token
    return f"{token[:6]}...{token[-4:]}"


def _decrypt_connection_token(value: str | None) -> str | None:
    return decrypt_text(value)


def _as_int(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _extract_response_payload(payload: dict[str, Any]) -> dict[str, Any]:
    nested = payload.get("response")
    if isinstance(nested, dict):
        return nested
    return payload


def _friendly_error_message(message: str) -> str:
    normalized = str(message or "").strip()
    lowered = normalized.lower()
    for key, hint in SHOPEE_ERROR_HINTS.items():
        if key in lowered:
            return f"{normalized} {hint}".strip()
    return normalized


def _load_option_catalog_items(kind: str, platform: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(OPTION_CATALOG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    platforms = payload.get("platforms")
    if not isinstance(platforms, dict):
        return []
    platform_payload = platforms.get(platform)
    if not isinstance(platform_payload, dict):
        return []
    raw_items = platform_payload.get(kind)
    if not isinstance(raw_items, list):
        return []
    return raw_items


def _parse_option_catalog(raw_value: str | None, *, kind: str, platform: str) -> list[dict[str, Any]]:
    parsed_items: list[dict[str, Any]]
    try:
        loaded = json.loads(str(raw_value or "[]"))
    except json.JSONDecodeError:
        loaded = []
    if isinstance(loaded, list):
        parsed_items = loaded
    else:
        parsed_items = []
    if not parsed_items:
        parsed_items = _load_option_catalog_items(kind, platform)
    return _normalize_option_catalog(parsed_items, field_name=kind, allow_blank=True)


def _normalize_option_catalog(
    items: list[dict[str, Any]] | None,
    *,
    field_name: str,
    allow_blank: bool = False,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for index, raw_item in enumerate(items or []):
        if not isinstance(raw_item, dict):
            if allow_blank:
                continue
            raise ValueError(f"{field_name}[{index}] must be an object")
        option_id = _as_int(raw_item.get("id"))
        label = str(raw_item.get("label") or "").strip()
        description = str(raw_item.get("description") or "").strip()
        parent_id = _as_int(raw_item.get("parent_id"))
        if parent_id is not None and parent_id <= 0:
            parent_id = None
        raw_is_leaf = raw_item.get("is_leaf")
        if isinstance(raw_is_leaf, bool):
            is_leaf: bool | None = raw_is_leaf
        elif raw_is_leaf in (None, ""):
            is_leaf = None
        else:
            is_leaf = str(raw_is_leaf).strip().lower() in {"1", "true", "yes", "leaf"}
        raw_tags = raw_item.get("tags")
        if isinstance(raw_tags, list):
            tags = [str(item).strip() for item in raw_tags if str(item).strip()]
        elif isinstance(raw_tags, str):
            tags = [item.strip() for item in raw_tags.split("|") if item.strip()]
        else:
            tags = []
        if not option_id or not label:
            if allow_blank:
                continue
            raise ValueError(f"{field_name}[{index}] must include numeric id and label")
        if option_id in seen_ids:
            continue
        normalized_item = {
            "id": int(option_id),
            "label": label,
            "description": description,
        }
        if parent_id is not None:
            normalized_item["parent_id"] = int(parent_id)
        if is_leaf is not None:
            normalized_item["is_leaf"] = bool(is_leaf)
        if tags:
            normalized_item["tags"] = tags
        normalized.append(normalized_item)
        seen_ids.add(int(option_id))
    return normalized


def _with_selected_option(
    options: list[dict[str, Any]],
    *,
    selected_id: int | None,
    fallback_label: str,
) -> list[dict[str, Any]]:
    if not selected_id:
        return options
    if any(_as_int(item.get("id")) == selected_id for item in options):
        return options
    return [
        {
            "id": int(selected_id),
            "label": f"{fallback_label} ({selected_id})",
            "description": "Imported from the currently configured publish default.",
            "is_leaf": None,
            "tags": ["selected-default"],
        },
        *options,
    ]


def _find_option_by_id(options: list[dict[str, Any]], option_id: int | None) -> dict[str, Any] | None:
    if not option_id:
        return None
    for item in options:
        if _as_int(item.get("id")) == int(option_id):
            return item
    return None


def inspect_publish_config(publish_config: dict[str, Any]) -> dict[str, Any]:
    shop_id = _as_int(publish_config.get("shop_id"))
    category_id = _as_int(publish_config.get("default_category_id"))
    logistic_id = _as_int(publish_config.get("default_logistic_id"))
    category_options = list(publish_config.get("category_options") or [])
    logistic_options = list(publish_config.get("logistic_options") or [])
    category_option = _find_option_by_id(category_options, category_id)
    logistic_option = _find_option_by_id(logistic_options, logistic_id)

    live_issues: list[str] = []
    if not shop_id:
        live_issues.append("Shop routing is missing. Configure a shop_id before live Shopee publish.")
    if not category_id:
        live_issues.append("Default category is missing. Choose a Shopee category before live publish.")
    elif not category_options:
        live_issues.append("Category catalog is empty. Sync categories from Shopee before live publish.")
    elif category_option is None:
        live_issues.append("Default category is not in the synced catalog. Resync categories or choose a valid leaf category.")
    elif category_option.get("is_leaf") is False:
        live_issues.append("Default category is not a leaf category. Choose a leaf Shopee category before live publish.")
    elif category_option.get("is_leaf") is None:
        live_issues.append("Default category is missing leaf metadata. Resync categories before live publish.")

    if not logistic_id:
        live_issues.append("Default logistic channel is missing. Choose a Shopee logistic channel before live publish.")
    elif logistic_options and logistic_option is None:
        live_issues.append("Default logistic channel is not in the synced catalog. Resync logistics or choose a valid channel.")

    return {
        "live_ready": len(live_issues) == 0,
        "live_issues": live_issues,
        "category_selection": {
            "id": category_id,
            "exists": category_option is not None,
            "label": str(category_option.get("label") or "") if category_option else None,
            "description": str(category_option.get("description") or "") if category_option else None,
            "parent_id": _as_int(category_option.get("parent_id")) if category_option else None,
            "is_leaf": category_option.get("is_leaf") if category_option else None,
            "tags": list(category_option.get("tags") or []) if category_option else [],
        },
        "logistic_selection": {
            "id": logistic_id,
            "exists": logistic_option is not None or logistic_id is None,
            "label": str(logistic_option.get("label") or "") if logistic_option else None,
            "description": str(logistic_option.get("description") or "") if logistic_option else None,
            "parent_id": _as_int(logistic_option.get("parent_id")) if logistic_option else None,
            "is_leaf": logistic_option.get("is_leaf") if logistic_option else None,
            "tags": list(logistic_option.get("tags") or []) if logistic_option else [],
        },
    }


def validate_live_publish_config(publish_config: dict[str, Any]) -> dict[str, Any]:
    health = inspect_publish_config(publish_config)
    if not health["live_ready"]:
        raise ValueError(" ".join(health["live_issues"]))
    return health


def _extract_category_options(payload: dict[str, Any]) -> list[dict[str, Any]]:
    response_payload = _extract_response_payload(payload)
    raw_items = response_payload.get("category_list") or payload.get("category_list") or []
    options: list[dict[str, Any]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        option_id = _as_int(raw_item.get("category_id") or raw_item.get("id"))
        if not option_id:
            continue
        label = str(
            raw_item.get("display_category_name")
            or raw_item.get("category_name")
            or raw_item.get("name")
            or raw_item.get("original_category_name")
            or ""
        ).strip()
        if not label:
            label = f"Category {option_id}"
        description_parts: list[str] = []
        original_name = str(raw_item.get("original_category_name") or "").strip()
        if original_name and original_name != label:
            description_parts.append(f"Original: {original_name}")
        parent_id = _as_int(raw_item.get("parent_category_id"))
        if parent_id and parent_id > 0:
            description_parts.append(f"Parent: {parent_id}")
        if raw_item.get("has_children") is True:
            description_parts.append("Has children")
        options.append(
            {
                "id": int(option_id),
                "label": label,
                "description": " | ".join(description_parts),
                "parent_id": parent_id,
                "is_leaf": raw_item.get("has_children") is not True,
                "tags": ["leaf" if raw_item.get("has_children") is not True else "branch"],
            }
        )
    return _normalize_option_catalog(options, field_name="category_options", allow_blank=True)


def _extract_logistic_options(payload: dict[str, Any]) -> list[dict[str, Any]]:
    response_payload = _extract_response_payload(payload)
    raw_items = (
        response_payload.get("logistics_channel_list")
        or response_payload.get("logistic_channel_list")
        or response_payload.get("channel_list")
        or payload.get("logistics_channel_list")
        or payload.get("logistic_channel_list")
        or payload.get("channel_list")
        or []
    )
    options: list[dict[str, Any]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        option_id = _as_int(
            raw_item.get("logistic_id")
            or raw_item.get("logistics_channel_id")
            or raw_item.get("channel_id")
            or raw_item.get("id")
        )
        if not option_id:
            continue
        label = str(
            raw_item.get("logistic_name")
            or raw_item.get("logistics_channel_name")
            or raw_item.get("channel_name")
            or raw_item.get("name")
            or ""
        ).strip()
        if not label:
            label = f"Logistic {option_id}"
        description_parts: list[str] = []
        for flag_key, flag_label in (
            ("enabled", "Enabled"),
            ("preferred", "Preferred"),
            ("cod_enabled", "COD"),
        ):
            if raw_item.get(flag_key) is True:
                description_parts.append(flag_label)
        shipping_fee_type = str(raw_item.get("shipping_fee_type") or "").strip()
        if shipping_fee_type:
            description_parts.append(f"Fee: {shipping_fee_type}")
        description = str(raw_item.get("description") or "").strip()
        if description:
            description_parts.append(description)
        tags: list[str] = []
        for flag_key, tag_value in (
            ("enabled", "enabled"),
            ("preferred", "preferred"),
            ("cod_enabled", "cod"),
        ):
            if raw_item.get(flag_key) is True:
                tags.append(tag_value)
        if shipping_fee_type:
            tags.append(shipping_fee_type.lower())
        options.append(
            {
                "id": int(option_id),
                "label": label,
                "description": " | ".join(description_parts),
                "tags": tags,
            }
        )
    return _normalize_option_catalog(options, field_name="logistic_options", allow_blank=True)


def serialize_publish_config(config: ShopeePublishConfig | None, platform: str) -> dict[str, Any]:
    default = _default_publish_config(platform)
    if config is None:
        resolved = default
    else:
        resolved = {
            "platform": platform,
            "marketplace": get_platform_marketplace(platform),
            "shop_id": config.shop_id if config.shop_id is not None else default["shop_id"],
            "default_category_id": (
                config.default_category_id if config.default_category_id is not None else default["default_category_id"]
            ),
            "default_logistic_id": (
                config.default_logistic_id if config.default_logistic_id is not None else default["default_logistic_id"]
            ),
            "category_options": _parse_option_catalog(
                config.category_options_json,
                kind="category_options",
                platform=platform,
            ),
            "logistic_options": _parse_option_catalog(
                config.logistic_options_json,
                kind="logistic_options",
                platform=platform,
            ),
            "default_weight_kg": float(config.default_weight_kg or default["default_weight_kg"]),
            "item_status": _normalize_item_status(config.item_status or default["item_status"]),
            "upload_images": bool(config.upload_images),
            "notes": config.notes or "",
            "source": "database",
            "updated_by_user_id": config.updated_by_user_id,
            "created_at": config.created_at,
            "updated_at": config.updated_at,
        }

    if not resolved.get("category_options"):
        resolved["category_options"] = _normalize_option_catalog(
            _load_option_catalog_items("category_options", platform),
            field_name="category_options",
            allow_blank=True,
        )
    if not resolved.get("logistic_options"):
        resolved["logistic_options"] = _normalize_option_catalog(
            _load_option_catalog_items("logistic_options", platform),
            field_name="logistic_options",
            allow_blank=True,
        )
    resolved["category_options"] = _with_selected_option(
        list(resolved.get("category_options") or []),
        selected_id=_as_int(resolved.get("default_category_id")),
        fallback_label="Current category",
    )
    resolved["logistic_options"] = _with_selected_option(
        list(resolved.get("logistic_options") or []),
        selected_id=_as_int(resolved.get("default_logistic_id")),
        fallback_label="Current logistic channel",
    )
    missing_fields = [
        field_name
        for field_name in ("shop_id", "default_category_id", "default_logistic_id")
        if resolved.get(field_name) in (None, "")
    ]
    resolved["configured"] = len(missing_fields) == 0
    resolved["missing_fields"] = missing_fields
    resolved.update(inspect_publish_config(resolved))
    return resolved


def resolve_publish_config(db: Session, platform: str) -> dict[str, Any]:
    config = db.query(ShopeePublishConfig).filter(ShopeePublishConfig.platform == platform).first()
    return serialize_publish_config(config, platform)


def list_publish_configs(db: Session) -> list[dict[str, Any]]:
    return [resolve_publish_config(db, platform) for platform in SHOPEE_MARKETS]


def upsert_publish_config(
    db: Session,
    *,
    platform: str,
    shop_id: int | None = None,
    default_category_id: int | None = None,
    default_logistic_id: int | None = None,
    category_options: list[dict[str, Any]] | None = None,
    logistic_options: list[dict[str, Any]] | None = None,
    default_weight_kg: float | None = None,
    item_status: str | None = None,
    upload_images: bool | None = None,
    notes: str | None = None,
    updated_by_user_id: str | None = None,
) -> ShopeePublishConfig:
    if not supports_platform(platform):
        raise ValueError(f"Unsupported Shopee platform: {platform}")

    config = db.query(ShopeePublishConfig).filter(ShopeePublishConfig.platform == platform).first()
    if config is None:
        config = ShopeePublishConfig(
            id=f"shpcfg_{uuid.uuid4().hex[:12]}",
            platform=platform,
            marketplace=get_platform_marketplace(platform),
        )

    if default_weight_kg is not None and default_weight_kg <= 0:
        raise ValueError("default_weight_kg must be positive")

    config.marketplace = get_platform_marketplace(platform)
    config.shop_id = shop_id
    config.default_category_id = default_category_id
    config.default_logistic_id = default_logistic_id
    if category_options is not None:
        config.category_options_json = json.dumps(
            _normalize_option_catalog(category_options, field_name="category_options"),
            ensure_ascii=False,
        )
    if logistic_options is not None:
        config.logistic_options_json = json.dumps(
            _normalize_option_catalog(logistic_options, field_name="logistic_options"),
            ensure_ascii=False,
        )
    if default_weight_kg is not None:
        config.default_weight_kg = float(default_weight_kg)
    config.item_status = _normalize_item_status(item_status)
    if upload_images is not None:
        config.upload_images = bool(upload_images)
    config.notes = str(notes or "")
    config.updated_by_user_id = updated_by_user_id

    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def _get_partner_credentials() -> tuple[str, str]:
    settings = get_settings()
    partner_id = str(settings.SHOPEE_PARTNER_ID or "").strip()
    partner_key = str(settings.SHOPEE_PARTNER_KEY or "").strip()
    if not partner_id or not partner_key:
        raise ValueError("Shopee partner credentials are not configured")
    return partner_id, partner_key


def sign_request(
    *,
    path: str,
    timestamp: int,
    access_token: str | None = None,
    shop_id: int | None = None,
) -> str:
    partner_id, partner_key = _get_partner_credentials()
    base_string = f"{partner_id}{path}{timestamp}"
    if access_token:
        base_string += access_token
    if shop_id:
        base_string += str(shop_id)
    return hmac.new(
        partner_key.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def build_auth_url(platform: str, redirect_url: str | None = None, timestamp: int | None = None) -> dict[str, Any]:
    settings = get_settings()
    if not supports_platform(platform):
        raise ValueError(f"Unsupported Shopee platform: {platform}")

    resolved_timestamp = int(timestamp or time.time())
    path = "/api/v2/shop/auth_partner"
    redirect = str(redirect_url or settings.SHOPEE_REDIRECT_URL or "").strip()
    if not redirect:
        raise ValueError("SHOPEE_REDIRECT_URL is not configured")
    redirect = append_redirect_params(redirect, {"platform": platform})

    partner_id, _ = _get_partner_credentials()
    sign = sign_request(path=path, timestamp=resolved_timestamp)
    query = urlencode(
        {
            "partner_id": partner_id,
            "timestamp": resolved_timestamp,
            "sign": sign,
            "redirect": redirect,
        }
    )
    auth_url = f"{str(settings.SHOPEE_API_BASE_URL).rstrip('/')}{path}?{query}"
    return {
        "platform": platform,
        "marketplace": get_platform_marketplace(platform),
        "auth_url": auth_url,
        "redirect": redirect,
        "timestamp": resolved_timestamp,
        "path": path,
        "partner_id": partner_id,
        "shop_id": get_platform_shop_id(platform),
        "sign": sign,
        "signing_mode": "partner_path_timestamp",
    }


def append_redirect_params(redirect_url: str, params: dict[str, str]) -> str:
    parsed = urlsplit(redirect_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in params.items():
        query[key] = value
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def _post_auth_payload(
    *,
    path: str,
    body: dict[str, Any],
    timeout_seconds: float = 20.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    settings = get_settings()
    partner_id, _ = _get_partner_credentials()
    timestamp = int(time.time())
    sign = sign_request(path=path, timestamp=timestamp)
    params = {
        "partner_id": partner_id,
        "timestamp": timestamp,
        "sign": sign,
    }
    url = f"{str(settings.SHOPEE_API_BASE_URL).rstrip('/')}{path}"
    response = httpx.post(url, params=params, json=body, timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        message = payload.get("message") or payload.get("error")
        raise RuntimeError(_friendly_error_message(str(message)))
    return payload, params


def exchange_token(
    *,
    platform: str,
    code: str,
    shop_id: int | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    if not supports_platform(platform):
        raise ValueError(f"Unsupported Shopee platform: {platform}")

    path = "/api/v2/auth/token/get"
    resolved_shop_id = shop_id or get_platform_shop_id(platform)
    if not resolved_shop_id:
        raise ValueError(f"{platform} is missing shop_id")

    partner_id, _ = _get_partner_credentials()
    body = {
        "code": code,
        "partner_id": int(partner_id),
        "shop_id": int(resolved_shop_id),
    }
    payload, params = _post_auth_payload(path=path, body=body, timeout_seconds=timeout_seconds)

    return {
        "platform": platform,
        "marketplace": get_platform_marketplace(platform),
        "shop_id": int(payload.get("shop_id") or resolved_shop_id),
        "merchant_id": payload.get("merchant_id"),
        "access_token": payload.get("access_token"),
        "refresh_token": payload.get("refresh_token"),
        "expire_in": payload.get("expire_in"),
        "request_id": payload.get("request_id"),
        "signing_mode": "partner_path_timestamp",
        "signed_path": path,
        "signed_query": params,
        "raw": payload,
    }


def refresh_access_token(
    *,
    platform: str,
    refresh_token: str,
    shop_id: int,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    if not supports_platform(platform):
        raise ValueError(f"Unsupported Shopee platform: {platform}")

    path = "/api/v2/auth/access_token/get"
    partner_id, _ = _get_partner_credentials()
    body = {
        "refresh_token": refresh_token,
        "partner_id": int(partner_id),
        "shop_id": int(shop_id),
    }
    payload, params = _post_auth_payload(path=path, body=body, timeout_seconds=timeout_seconds)
    next_refresh_token = payload.get("refresh_token") or refresh_token
    return {
        "platform": platform,
        "marketplace": get_platform_marketplace(platform),
        "shop_id": int(payload.get("shop_id") or shop_id),
        "merchant_id": _as_int(payload.get("merchant_id")),
        "access_token": payload.get("access_token"),
        "refresh_token": next_refresh_token,
        "expire_in": _as_int(payload.get("expire_in")),
        "request_id": payload.get("request_id"),
        "signing_mode": "partner_path_timestamp",
        "signed_path": path,
        "signed_query": params,
        "raw": payload,
    }


def upsert_connection(
    db: Session,
    *,
    platform: str,
    token_payload: dict[str, Any],
    connected_by_user_id: str | None = None,
) -> ShopeeConnection:
    shop_id = _as_int(token_payload.get("shop_id"))
    if not shop_id:
        raise ValueError("Shopee token payload is missing shop_id")

    connection = (
        db.query(ShopeeConnection)
        .filter(ShopeeConnection.platform == platform, ShopeeConnection.shop_id == int(shop_id))
        .first()
    )
    now = _utcnow()
    expire_in = _as_int(token_payload.get("expire_in"), ACCESS_TOKEN_DEFAULT_SECONDS) or ACCESS_TOKEN_DEFAULT_SECONDS
    next_refresh_token = str(token_payload.get("refresh_token") or "").strip() or None
    if connection is None:
        connection = ShopeeConnection(
            id=f"shpconn_{uuid.uuid4().hex[:12]}",
            platform=platform,
            marketplace=get_platform_marketplace(platform),
            shop_id=int(shop_id),
        )

    connection.marketplace = get_platform_marketplace(platform)
    connection.partner_id = str(get_settings().SHOPEE_PARTNER_ID or "").strip()
    connection.shop_id = int(shop_id)
    connection.merchant_id = _as_int(token_payload.get("merchant_id"))
    connection.access_token = encrypt_text(token_payload.get("access_token"))
    connection.refresh_token = encrypt_text(next_refresh_token)
    connection.access_token_expires_at = now + timedelta(seconds=expire_in)
    if next_refresh_token:
        connection.refresh_token_expires_at = now + timedelta(days=REFRESH_TOKEN_DEFAULT_DAYS)
    connection.last_request_id = str(token_payload.get("request_id") or "")
    if connected_by_user_id:
        connection.connected_by_user_id = connected_by_user_id

    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


def get_connection(
    db: Session,
    *,
    platform: str,
    shop_id: int | None = None,
) -> ShopeeConnection:
    query = db.query(ShopeeConnection).filter(ShopeeConnection.platform == platform)
    if shop_id is not None:
        connection = query.filter(ShopeeConnection.shop_id == int(shop_id)).first()
        if connection is None:
            raise ValueError(f"No Shopee connection found for {platform} / shop_id {shop_id}")
        return connection

    items = query.order_by(ShopeeConnection.updated_at.desc(), ShopeeConnection.created_at.desc()).all()
    if not items:
        raise ValueError(f"No Shopee connection found for {platform}")
    if len(items) > 1:
        raise ValueError(f"Multiple Shopee connections found for {platform}; please specify shop_id")
    return items[0]


def list_connections(db: Session) -> list[ShopeeConnection]:
    return (
        db.query(ShopeeConnection)
        .order_by(ShopeeConnection.updated_at.desc(), ShopeeConnection.created_at.desc())
        .all()
    )


def serialize_connection(connection: ShopeeConnection) -> dict[str, Any]:
    now = _utcnow()
    expires_at = connection.access_token_expires_at
    is_expired = bool(expires_at and expires_at <= now)
    needs_refresh = bool(not expires_at or expires_at <= now + timedelta(seconds=REFRESH_GRACE_SECONDS))
    access_token = _decrypt_connection_token(connection.access_token)
    refresh_token = _decrypt_connection_token(connection.refresh_token)
    return {
        "id": connection.id,
        "platform": connection.platform,
        "marketplace": connection.marketplace,
        "partner_id": connection.partner_id,
        "shop_id": connection.shop_id,
        "merchant_id": connection.merchant_id,
        "access_token_preview": _token_preview(access_token),
        "refresh_token_preview": _token_preview(refresh_token),
        "access_token_expires_at": connection.access_token_expires_at,
        "refresh_token_expires_at": connection.refresh_token_expires_at,
        "is_access_token_expired": is_expired,
        "needs_refresh": needs_refresh,
        "last_request_id": connection.last_request_id or None,
        "connected_by_user_id": connection.connected_by_user_id,
        "created_at": connection.created_at,
        "updated_at": connection.updated_at,
    }


def get_connection_refresh_token(connection: ShopeeConnection) -> str | None:
    return _decrypt_connection_token(connection.refresh_token)


def get_connection_access_token(connection: ShopeeConnection) -> str | None:
    return _decrypt_connection_token(connection.access_token)


def connection_needs_refresh(connection: ShopeeConnection) -> bool:
    expires_at = connection.access_token_expires_at
    if not expires_at:
        return True
    return expires_at <= _utcnow() + timedelta(seconds=REFRESH_GRACE_SECONDS)


def ensure_connection_ready(
    db: Session,
    *,
    platform: str,
    shop_id: int | None = None,
    connected_by_user_id: str | None = None,
    timeout_seconds: float = 20.0,
) -> tuple[ShopeeConnection, bool]:
    connection = get_connection(db, platform=platform, shop_id=shop_id)
    if not connection_needs_refresh(connection):
        return connection, False

    refresh_token = get_connection_refresh_token(connection)
    if not refresh_token:
        raise ValueError(f"{platform} / {connection.shop_id} is missing refresh_token")

    payload = refresh_access_token(
        platform=platform,
        refresh_token=refresh_token,
        shop_id=connection.shop_id,
        timeout_seconds=timeout_seconds,
    )
    refreshed = upsert_connection(
        db,
        platform=platform,
        token_payload=payload,
        connected_by_user_id=connected_by_user_id,
    )
    return refreshed, True


def _request_with_connection(
    *,
    connection: ShopeeConnection,
    path: str,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    form_data: dict[str, Any] | None = None,
    files: Any = None,
    timeout_seconds: float = 20.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    settings = get_settings()
    partner_id, _ = _get_partner_credentials()
    access_token = get_connection_access_token(connection)
    if not access_token:
        raise ValueError(f"{connection.platform} / {connection.shop_id} is missing access_token")

    timestamp = int(time.time())
    signed_query = {
        "partner_id": partner_id,
        "timestamp": timestamp,
        "access_token": access_token,
        "shop_id": connection.shop_id,
        "sign": sign_request(
            path=path,
            timestamp=timestamp,
            access_token=access_token,
            shop_id=connection.shop_id,
        ),
    }
    if params:
        signed_query.update({key: value for key, value in params.items() if value is not None})

    url = f"{str(settings.SHOPEE_API_BASE_URL).rstrip('/')}{path}"
    request_kwargs: dict[str, Any] = {
        "params": signed_query,
        "timeout": timeout_seconds,
    }
    if json_body is not None:
        request_kwargs["json"] = json_body
    if form_data is not None:
        request_kwargs["data"] = form_data
    if files is not None:
        request_kwargs["files"] = files

    response = httpx.request(method.upper(), url, **request_kwargs)
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        message = payload.get("message") or payload.get("error")
        raise RuntimeError(_friendly_error_message(str(message)))
    return payload, signed_query


def call_shop_api(
    db: Session,
    *,
    platform: str,
    path: str,
    shop_id: int | None = None,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    form_data: dict[str, Any] | None = None,
    files: Any = None,
    connected_by_user_id: str | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    connection, auto_refreshed = ensure_connection_ready(
        db,
        platform=platform,
        shop_id=shop_id,
        connected_by_user_id=connected_by_user_id,
        timeout_seconds=timeout_seconds,
    )
    try:
        payload, signed_query = _request_with_connection(
            connection=connection,
            path=path,
            method=method,
            params=params,
            json_body=json_body,
            form_data=form_data,
            files=files,
            timeout_seconds=timeout_seconds,
        )
    except RuntimeError as exc:
        message = str(exc).lower()
        if "error_auth" not in message and "invalid access_token" not in message:
            raise
        refresh_token = get_connection_refresh_token(connection)
        if not refresh_token:
            raise
        refreshed_payload = refresh_access_token(
            platform=platform,
            refresh_token=refresh_token,
            shop_id=connection.shop_id,
            timeout_seconds=timeout_seconds,
        )
        connection = upsert_connection(
            db,
            platform=platform,
            token_payload=refreshed_payload,
            connected_by_user_id=connected_by_user_id,
        )
        auto_refreshed = True
        payload, signed_query = _request_with_connection(
            connection=connection,
            path=path,
            method=method,
            params=params,
            json_body=json_body,
            form_data=form_data,
            files=files,
            timeout_seconds=timeout_seconds,
        )

    return {
        "platform": platform,
        "marketplace": get_platform_marketplace(platform),
        "shop_id": connection.shop_id,
        "signed_path": path,
        "signed_query": signed_query,
        "auto_refreshed": auto_refreshed,
        "connection": serialize_connection(connection),
        "raw": payload,
    }


def get_shop_info(
    db: Session,
    *,
    platform: str,
    shop_id: int | None = None,
    connected_by_user_id: str | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    # Inference from Shopee Open Platform V2 naming conventions for the first live read call.
    # Verify the exact response shape in your partner app's official docs during production rollout.
    result = call_shop_api(
        db,
        platform=platform,
        path="/api/v2/shop/get_shop_info",
        shop_id=shop_id,
        method="GET",
        connected_by_user_id=connected_by_user_id,
        timeout_seconds=timeout_seconds,
    )
    raw = result["raw"]
    result["shop_name"] = raw.get("shop_name")
    result["region"] = raw.get("region")
    result["status"] = raw.get("status")
    result["sip_affi_shops"] = list(raw.get("sip_affi_shops") or [])
    return result


def fetch_category_options(
    db: Session,
    *,
    platform: str,
    shop_id: int | None = None,
    language: str | None = None,
    connected_by_user_id: str | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    result = call_shop_api(
        db,
        platform=platform,
        path=CATEGORY_LIST_PATH,
        shop_id=shop_id,
        method="GET",
        params={"language": str(language or platform_locale(platform)).strip()},
        connected_by_user_id=connected_by_user_id,
        timeout_seconds=timeout_seconds,
    )
    return {
        **result,
        "options": _extract_category_options(result["raw"]),
        "request_path": CATEGORY_LIST_PATH,
    }


def fetch_logistic_options(
    db: Session,
    *,
    platform: str,
    shop_id: int | None = None,
    connected_by_user_id: str | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    result = call_shop_api(
        db,
        platform=platform,
        path=LOGISTIC_CHANNEL_LIST_PATH,
        shop_id=shop_id,
        method="GET",
        connected_by_user_id=connected_by_user_id,
        timeout_seconds=timeout_seconds,
    )
    return {
        **result,
        "options": _extract_logistic_options(result["raw"]),
        "request_path": LOGISTIC_CHANNEL_LIST_PATH,
    }


def sync_publish_option_catalogs(
    db: Session,
    *,
    platform: str,
    shop_id: int | None = None,
    language: str | None = None,
    include_categories: bool = True,
    include_logistics: bool = True,
    connected_by_user_id: str | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    current = resolve_publish_config(db, platform)
    resolved_shop_id = shop_id or _as_int(current.get("shop_id")) or get_platform_shop_id(platform)
    if not resolved_shop_id:
        raise ValueError(f"{platform} is missing shop_id in config or env")
    if not include_categories and not include_logistics:
        raise ValueError("At least one catalog must be selected for sync")

    category_result: dict[str, Any] | None = None
    logistic_result: dict[str, Any] | None = None
    category_options = list(current.get("category_options") or [])
    logistic_options = list(current.get("logistic_options") or [])
    auto_refreshed = False

    if include_categories:
        category_result = fetch_category_options(
            db,
            platform=platform,
            shop_id=resolved_shop_id,
            language=language,
            connected_by_user_id=connected_by_user_id,
            timeout_seconds=timeout_seconds,
        )
        category_options = list(category_result["options"])
        auto_refreshed = auto_refreshed or bool(category_result.get("auto_refreshed"))

    if include_logistics:
        logistic_result = fetch_logistic_options(
            db,
            platform=platform,
            shop_id=resolved_shop_id,
            connected_by_user_id=connected_by_user_id,
            timeout_seconds=timeout_seconds,
        )
        logistic_options = list(logistic_result["options"])
        auto_refreshed = auto_refreshed or bool(logistic_result.get("auto_refreshed"))

    config = upsert_publish_config(
        db,
        platform=platform,
        shop_id=resolved_shop_id,
        default_category_id=_as_int(current.get("default_category_id")),
        default_logistic_id=_as_int(current.get("default_logistic_id")),
        category_options=category_options,
        logistic_options=logistic_options,
        default_weight_kg=float(current.get("default_weight_kg") or 0.35),
        item_status=str(current.get("item_status") or "UNLIST"),
        upload_images=bool(current.get("upload_images", True)),
        notes=str(current.get("notes") or ""),
        updated_by_user_id=connected_by_user_id,
    )
    return {
        "config": serialize_publish_config(config, platform),
        "synced": {
            "platform": platform,
            "shop_id": resolved_shop_id,
            "language": str(language or platform_locale(platform)).strip(),
            "auto_refreshed": auto_refreshed,
            "category_count": len(category_options),
            "logistic_count": len(logistic_options),
            "category_request_id": (
                str(category_result["raw"].get("request_id")) if category_result and category_result.get("raw") else None
            ),
            "logistic_request_id": (
                str(logistic_result["raw"].get("request_id")) if logistic_result and logistic_result.get("raw") else None
            ),
            "category_request_path": category_result.get("request_path") if category_result else None,
            "logistic_request_path": logistic_result.get("request_path") if logistic_result else None,
        },
    }


def publish_listing(product: Product, translation: dict[str, Any], platform: str) -> dict[str, Any]:
    market = SHOPEE_MARKETS[platform]
    base_price = float(translation.get("price") or convert_price_from_cny(float(product.price), market["currency"]))
    final_price = round(base_price * float(market["markup"]), 2)
    original_title = str(translation["title"])
    title = original_title[:120]
    warnings: list[str] = []
    if len(original_title) > 120:
        warnings.append("标题已裁剪到 Shopee 建议长度 120 字符。")
    return {
        "platform": platform,
        "marketplace": market["marketplace"],
        "status": "prepared",
        "mode": "preview",
        "locale": market["locale"],
        "currency": market["currency"],
        "price": final_price,
        "listing_id": f"shp_{platform.split('_')[-1]}_{product.id}",
        "title": title,
        "highlights": list(translation.get("highlights") or [])[:3],
        "marketplace_url": f"{market['domain']}/product/{product.id}",
        "warnings": warnings,
        "shop_id": get_platform_shop_id(platform),
    }


def _resolve_listing_price(product: Product, translation: dict[str, Any], platform: str) -> float:
    market = SHOPEE_MARKETS[platform]
    base_price = float(translation.get("price") or convert_price_from_cny(float(product.price), market["currency"]))
    return round(base_price * float(market["markup"]), 2)


def _normalize_listing_title(title: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    normalized = title[:120]
    if len(title) > 120:
        warnings.append("Shopee title exceeded 120 characters and was truncated automatically.")
    return normalized, warnings


def _extract_weight_kg(product: Product, publish_config: dict[str, Any] | None = None) -> float:
    specs = product.specs or {}
    candidates = [specs.get("weight_kg"), specs.get("weightKg"), specs.get("weight")]
    for value in candidates:
        try:
            return round(float(value), 3)
        except (TypeError, ValueError):
            continue
    default_weight = (publish_config or {}).get("default_weight_kg")
    if default_weight in (None, ""):
        default_weight = getattr(get_settings(), "SHOPEE_DEFAULT_WEIGHT_KG", 0.35)
    return round(float(default_weight or 0.35), 3)


def build_listing_payload(
    product: Product,
    translation: dict[str, Any],
    platform: str,
    publish_config: dict[str, Any] | None = None,
    uploaded_image_ids: list[str] | None = None,
) -> dict[str, Any]:
    market = SHOPEE_MARKETS[platform]
    resolved_config = publish_config or _default_publish_config(platform)
    validate_live_publish_config(resolved_config)
    category_id = _as_int(resolved_config.get("default_category_id"))
    if not category_id:
        raise ValueError("SHOPEE_DEFAULT_CATEGORY_ID is required for live Shopee publish")

    original_title = str(translation["title"])
    title, warnings = _normalize_listing_title(original_title)
    final_price = _resolve_listing_price(product, translation, platform)
    image_urls = [str(item).strip() for item in list(product.images or []) if str(item).strip()][:9]
    image_ids = [str(item).strip() for item in list(uploaded_image_ids or []) if str(item).strip()][:9]
    if not image_urls and not image_ids:
        raise ValueError("Shopee live publish requires at least one product image URL")

    payload: dict[str, Any] = {
        "item_name": title,
        "description": str(translation.get("description") or product.description or title),
        "item_sku": product.id,
        "category_id": category_id,
        "original_price": final_price,
        "normal_stock": max(int(product.stock or 0), 0),
        "item_status": _normalize_item_status(resolved_config.get("item_status")),
        "condition": "NEW",
        "weight": _extract_weight_kg(product, resolved_config),
    }
    if image_ids:
        payload["image"] = {"image_id_list": image_ids}
    else:
        payload["image"] = {"image_url_list": image_urls}

    logistic_id = _as_int(resolved_config.get("default_logistic_id"))
    if logistic_id:
        payload["logistic_info"] = [{"logistic_id": logistic_id, "enabled": True}]

    return {
        "platform": platform,
        "marketplace": market["marketplace"],
        "locale": market["locale"],
        "currency": market["currency"],
        "price": final_price,
        "title": title,
        "highlights": list(translation.get("highlights") or [])[:3],
        "warnings": warnings,
        "publish_config": resolved_config,
        "payload": payload,
    }


def _guess_upload_filename(image_url: str, content_type: str | None) -> str:
    guessed = mimetypes.guess_extension(str(content_type or "").split(";")[0].strip()) or ""
    path = urlsplit(image_url).path
    suffix = guessed or path[path.rfind(".") :] if "." in path else guessed
    suffix = suffix if suffix.startswith(".") else f".{suffix}" if suffix else ".jpg"
    return f"product-image{suffix or '.jpg'}"


def _download_image_asset(image_url: str, timeout_seconds: float = 20.0) -> tuple[bytes, str, str]:
    response = httpx.get(image_url, timeout=timeout_seconds, follow_redirects=True)
    response.raise_for_status()
    content_type = str(response.headers.get("content-type") or "image/jpeg")
    filename = _guess_upload_filename(image_url, content_type)
    return response.content, content_type, filename


def upload_listing_image(
    db: Session,
    *,
    platform: str,
    image_url: str,
    shop_id: int | None = None,
    connected_by_user_id: str | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    content, content_type, filename = _download_image_asset(image_url, timeout_seconds=timeout_seconds)
    result = call_shop_api(
        db,
        platform=platform,
        path=MEDIA_UPLOAD_IMAGE_PATH,
        shop_id=shop_id,
        method="POST",
        files={"image": (filename, content, content_type)},
        connected_by_user_id=connected_by_user_id,
        timeout_seconds=timeout_seconds,
    )
    raw = result["raw"]
    response_payload = _extract_response_payload(raw)
    image_id = (
        response_payload.get("image_id")
        or (response_payload.get("image_info") or {}).get("image_id")
        or ((response_payload.get("image_info_list") or [{}])[0]).get("image_id")
    )
    if not image_id:
        raise RuntimeError("Shopee image upload succeeded but did not return image_id")
    return {
        "platform": platform,
        "shop_id": result["shop_id"],
        "image_url": image_url,
        "image_id": str(image_id),
        "request_path": MEDIA_UPLOAD_IMAGE_PATH,
        "request_id": raw.get("request_id"),
        "raw": raw,
    }


def prepare_listing_images(
    db: Session,
    *,
    product: Product,
    platform: str,
    publish_config: dict[str, Any],
    shop_id: int | None = None,
    connected_by_user_id: str | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    image_urls = [str(item).strip() for item in list(product.images or []) if str(item).strip()][:9]
    if not image_urls:
        raise ValueError("Shopee live publish requires at least one product image URL")

    if not bool(publish_config.get("upload_images", True)):
        return {
            "mode": "remote_url",
            "image_ids": [],
            "image_urls": image_urls,
            "uploads": [],
        }

    uploads = [
        upload_listing_image(
            db,
            platform=platform,
            image_url=image_url,
            shop_id=shop_id or _as_int(publish_config.get("shop_id")),
            connected_by_user_id=connected_by_user_id,
            timeout_seconds=timeout_seconds,
        )
        for image_url in image_urls
    ]
    return {
        "mode": "shopee_upload",
        "image_ids": [str(item["image_id"]) for item in uploads],
        "image_urls": image_urls,
        "uploads": uploads,
    }


def get_listing_status(
    db: Session,
    *,
    platform: str,
    item_id: str | int,
    shop_id: int | None = None,
    connected_by_user_id: str | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    result = call_shop_api(
        db,
        platform=platform,
        path=ITEM_BASE_INFO_PATH,
        shop_id=shop_id,
        method="GET",
        params={"item_id_list": str(item_id)},
        connected_by_user_id=connected_by_user_id,
        timeout_seconds=timeout_seconds,
    )
    raw = result["raw"]
    response_payload = _extract_response_payload(raw)
    items = list(response_payload.get("item_list") or raw.get("item_list") or [])
    item = items[0] if items else {}
    return {
        **result,
        "item_id": str(item_id),
        "listing_status": item.get("item_status") or item.get("status"),
        "item_name": item.get("item_name") or item.get("name"),
        "item": item,
    }


def publish_listing_live(
    db: Session,
    *,
    product: Product,
    translation: dict[str, Any],
    platform: str,
    shop_id: int | None = None,
    connected_by_user_id: str | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    publish_config = resolve_publish_config(db, platform)
    resolved_shop_id = shop_id or _as_int(publish_config.get("shop_id"))
    if not resolved_shop_id:
        raise ValueError(f"{platform} is missing shop_id in config or env")
    validate_live_publish_config(publish_config)
    image_bundle = prepare_listing_images(
        db,
        product=product,
        platform=platform,
        publish_config=publish_config,
        shop_id=resolved_shop_id,
        connected_by_user_id=connected_by_user_id,
        timeout_seconds=timeout_seconds,
    )
    preview = build_listing_payload(
        product,
        translation,
        platform,
        publish_config=publish_config,
        uploaded_image_ids=image_bundle["image_ids"],
    )
    request_payload = preview["payload"]
    result = call_shop_api(
        db,
        platform=platform,
        path=LIVE_ADD_ITEM_PATH,
        shop_id=resolved_shop_id,
        method="POST",
        json_body=request_payload,
        connected_by_user_id=connected_by_user_id,
        timeout_seconds=timeout_seconds,
    )
    raw = result["raw"]
    response_payload = _extract_response_payload(raw)
    item_id = response_payload.get("item_id") or response_payload.get("itemid")
    listing_id = str(item_id) if item_id is not None else None
    market = SHOPEE_MARKETS[platform]
    request_id = raw.get("request_id")
    response_shop_id = _as_int(result.get("shop_id")) or _as_int(result["connection"].get("shop_id"))
    return {
        "platform": platform,
        "marketplace": market["marketplace"],
        "status": "submitted",
        "mode": "live",
        "locale": preview["locale"],
        "currency": preview["currency"],
        "price": preview["price"],
        "listing_id": listing_id,
        "title": preview["title"],
        "highlights": preview["highlights"],
        "marketplace_url": f"{market['domain']}/product/{listing_id}" if listing_id else None,
        "warnings": preview["warnings"],
        "shop_id": response_shop_id,
        "request_path": LIVE_ADD_ITEM_PATH,
        "request_id": str(request_id) if request_id else None,
        "request_payload": request_payload,
        "image_mode": image_bundle["mode"],
        "uploaded_image_ids": image_bundle["image_ids"],
        "raw": raw,
        "connection": result["connection"],
    }


def sync_inventory(platform: str, stock: int) -> dict[str, Any]:
    market = SHOPEE_MARKETS[platform]
    return {
        "platform": platform,
        "status": "synced",
        "stock": stock,
        "currency": market["currency"],
        "message": f"{market['marketplace']} 库存已更新为 {stock}",
    }
