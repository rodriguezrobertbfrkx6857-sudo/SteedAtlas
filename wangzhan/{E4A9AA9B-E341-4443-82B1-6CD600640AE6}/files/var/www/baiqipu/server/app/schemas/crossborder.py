from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CrossborderTranslateRequest(BaseModel):
    product_id: str
    target_languages: list[str] = Field(default_factory=list, min_length=1, max_length=8)
    persist: bool = True


class LocalizedProductOut(BaseModel):
    locale: str
    locale_name: str
    market: str
    currency: str
    short_title: str
    title: str
    description: str
    tags: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    search_keywords: list[str] = Field(default_factory=list)
    price: float


class CrossborderTranslateOut(BaseModel):
    product_id: str
    source_locale: str = "zh-CN"
    translations: dict[str, LocalizedProductOut]


class CrossborderPublishRequest(BaseModel):
    product_id: str
    platforms: list[str] = Field(default_factory=list, min_length=1, max_length=8)
    use_localization: bool = True
    mode: str = Field(default="preview", pattern="^(preview|live)$")
    shop_id: int | None = None


class CrossborderPublishPlatformOut(BaseModel):
    platform: str
    marketplace: str
    status: str
    mode: str = "preview"
    locale: str
    currency: str
    price: float
    listing_id: str | None = None
    title: str
    highlights: list[str] = Field(default_factory=list)
    marketplace_url: str | None = None
    warnings: list[str] = Field(default_factory=list)
    shop_id: int | None = None
    record_id: str | None = None
    request_path: str | None = None
    request_id: str | None = None
    error: str | None = None


class CrossborderPublishOut(BaseModel):
    task_id: str
    status: str
    mode: str = "preview"
    platforms: dict[str, CrossborderPublishPlatformOut]


class CrossborderPublishRecordOut(BaseModel):
    id: str
    product_id: str
    platform: str
    marketplace: str
    mode: str
    status: str
    locale: str
    currency: str
    shop_id: int | None = None
    listing_id: str | None = None
    title: str
    price: float | None = None
    marketplace_url: str | None = None
    request_path: str | None = None
    request_id: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CrossborderPublishRecordListOut(BaseModel):
    product_id: str | None = None
    total_count: int
    items: list[CrossborderPublishRecordOut] = Field(default_factory=list)


class CrossborderPublishRecordDetailOut(CrossborderPublishRecordOut):
    warnings: list[str] = Field(default_factory=list)
    request_payload: dict[str, Any] = Field(default_factory=dict)
    response_payload: dict[str, Any] = Field(default_factory=dict)


class CrossborderSyncInventoryRequest(BaseModel):
    product_id: str
    quantity_change: int
    platforms: list[str] = Field(default_factory=list)


class CrossborderSyncInventoryPlatformOut(BaseModel):
    platform: str
    status: str
    stock: int
    currency: str
    message: str


class CrossborderSyncInventoryOut(BaseModel):
    product_id: str
    stock_before: int
    stock_after: int
    synced: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    platforms: dict[str, CrossborderSyncInventoryPlatformOut] = Field(default_factory=dict)


class CrossborderPlatformStatusOut(BaseModel):
    platform: str
    marketplace: str
    configured: bool
    mode: str
    missing_envs: list[str] = Field(default_factory=list)
    note: str


class CrossborderPlatformStatusSummaryOut(BaseModel):
    configured_count: int
    total_count: int


class CrossborderPlatformStatusResponseOut(BaseModel):
    summary: CrossborderPlatformStatusSummaryOut
    platforms: dict[str, CrossborderPlatformStatusOut]


class CrossborderShopeePublishSelectionOut(BaseModel):
    id: int | None = None
    exists: bool = False
    label: str | None = None
    description: str | None = None
    parent_id: int | None = None
    is_leaf: bool | None = None
    tags: list[str] = Field(default_factory=list)


class CrossborderShopeePublishConfigOut(BaseModel):
    platform: str
    marketplace: str
    shop_id: int | None = None
    default_category_id: int | None = None
    default_logistic_id: int | None = None
    configured: bool
    missing_fields: list[str] = Field(default_factory=list)
    live_ready: bool = False
    live_issues: list[str] = Field(default_factory=list)
    category_selection: CrossborderShopeePublishSelectionOut
    logistic_selection: CrossborderShopeePublishSelectionOut
    has_connected_shop: bool = False
    connection_shop_id: int | None = None


class CrossborderShopeePublishConfigListOut(BaseModel):
    total_count: int
    items: list[CrossborderShopeePublishConfigOut] = Field(default_factory=list)


class CrossborderShopeeAuthUrlOut(BaseModel):
    platform: str
    marketplace: str
    auth_url: str
    redirect: str
    timestamp: int
    path: str
    partner_id: str
    shop_id: int | None = None
    sign: str
    signing_mode: str


class CrossborderShopeeTokenExchangeRequest(BaseModel):
    platform: str
    code: str
    shop_id: int | None = None


class CrossborderShopeeRefreshRequest(BaseModel):
    platform: str
    shop_id: int | None = None


class CrossborderShopeeConnectionOut(BaseModel):
    id: str
    platform: str
    marketplace: str
    partner_id: str
    shop_id: int
    merchant_id: int | None = None
    access_token_preview: str | None = None
    refresh_token_preview: str | None = None
    access_token_expires_at: datetime | None = None
    refresh_token_expires_at: datetime | None = None
    is_access_token_expired: bool
    needs_refresh: bool
    last_request_id: str | None = None
    connected_by_user_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CrossborderShopeeConnectionSummaryOut(BaseModel):
    total_count: int
    expired_count: int
    healthy_count: int


class CrossborderShopeeConnectionListOut(BaseModel):
    summary: CrossborderShopeeConnectionSummaryOut
    items: list[CrossborderShopeeConnectionOut] = Field(default_factory=list)


class CrossborderShopeeShopInfoOut(BaseModel):
    platform: str
    marketplace: str
    shop_id: int
    signed_path: str
    signed_query: dict[str, Any] = Field(default_factory=dict)
    auto_refreshed: bool = False
    connection: CrossborderShopeeConnectionOut | None = None
    shop_name: str | None = None
    region: str | None = None
    status: str | None = None
    sip_affi_shops: list[Any] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class CrossborderShopeeTokenExchangeOut(BaseModel):
    platform: str
    marketplace: str
    shop_id: int
    merchant_id: int | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    expire_in: int | None = None
    request_id: str | None = None
    signing_mode: str
    signed_path: str
    signed_query: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)
    connection: CrossborderShopeeConnectionOut | None = None
