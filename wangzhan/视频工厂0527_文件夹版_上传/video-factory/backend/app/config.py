import json
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "百骑谱API"
    DEBUG: bool = True
    VERSION: str = "1.0.0"
    APP_PUBLIC_BASE_URL: str = "http://127.0.0.1:8000"

    # Database
    DATABASE_URL: str = "sqlite:///./baiqipu.db"

    # JWT
    SECRET_KEY: str = "baiqipu-dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ADMIN_BOOTSTRAP_PHONES: list[str] = []
    OPERATOR_BOOTSTRAP_PHONES: list[str] = []

    # Redis (optional)
    REDIS_URL: str = "redis://localhost:6379/0"
    WORKFLOW_RUNTIME_REDIS_ENABLED: bool = True
    WORKFLOW_RUNTIME_REDIS_PREFIX: str = "baiqipu:workflow:task:"
    WORKFLOW_RUNTIME_REDIS_TTL_SECONDS: int = 86400
    WORKFLOW_RUNTIME_REDIS_EVENT_LIMIT: int = 120

    # AI
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-5.4-mini"
    OPENAI_REASONING_EFFORT: str = "low"
    OPENAI_MAX_OUTPUT_TOKENS: int = 500
    OPENAI_TIMEOUT_SECONDS: float = 20.0
    AZURE_TTS_KEY: str = ""
    AZURE_TTS_REGION: str = ""
    RAG_TOP_K: int = 3

    # Video factory provider APIs. These are server-only; never put keys in frontend files.
    VIDEO_FACTORY_API_MODE: str = "auto"
    VIDEO_FACTORY_MEDIA_BASE_URL: str = "/generated"
    VIDEO_FACTORY_DOWNLOAD_REMOTE_MEDIA: bool = False
    VIDEO_FACTORY_GPT_API_KEY: str = ""
    VIDEO_FACTORY_GPT_BASE_URL: str = ""
    VIDEO_FACTORY_GPT_MODEL: str = ""
    VIDEO_FACTORY_GPT_API_PATH: str = "/chat/completions"
    VIDEO_FACTORY_GPT_API_STYLE: str = "chat_completions"
    VIDEO_FACTORY_GPT_MAX_TOKENS: int = 1800
    VIDEO_FACTORY_GPT_TIMEOUT_SECONDS: float = 60.0
    VIDEO_FACTORY_IMAGE_API_KEY: str = ""
    VIDEO_FACTORY_IMAGE_BASE_URL: str = ""
    VIDEO_FACTORY_IMAGE_MODEL: str = "gpt-image-2"
    VIDEO_FACTORY_IMAGE_API_PATH: str = "/images/generations"
    VIDEO_FACTORY_IMAGE_SIZE: str = "1024x1792"
    VIDEO_FACTORY_IMAGE_TIMEOUT_SECONDS: float = 120.0
    VIDEO_FACTORY_VEO_API_KEY: str = ""
    VIDEO_FACTORY_VEO_BASE_URL: str = ""
    VIDEO_FACTORY_VEO_MODEL: str = "veo-3.0-generate-001"
    VIDEO_FACTORY_VEO_FALLBACK_MODELS: str = ""
    VIDEO_FACTORY_AGENT_VIDEO_MODEL: str = ""
    VIDEO_FACTORY_AGENT_VIDEO_FALLBACK_MODELS: str = ""
    VIDEO_FACTORY_VEO_API_PATH: str = "/videos/generations"
    VIDEO_FACTORY_VEO_STATUS_API_PATH: str = ""
    VIDEO_FACTORY_VEO_REQUEST_FORMAT: str = "json"
    VIDEO_FACTORY_VEO_TIMEOUT_SECONDS: float = 180.0
    VIDEO_FACTORY_VEO_GENERATE_AUDIO: bool = True
    VIDEO_FACTORY_VEO_ENHANCE_PROMPT: bool = True
    VIDEO_FACTORY_VEO_MAX_CLIPS_PER_TASK: int = 1
    VIDEO_FACTORY_VEO_WAIT_FOR_COMPLETION: bool = True
    VIDEO_FACTORY_VEO_POLL_INTERVAL_SECONDS: float = 15.0
    VIDEO_FACTORY_VEO_MAX_POLL_ATTEMPTS: int = 60
    VIDEO_FACTORY_ASR_ENABLED: bool = True
    VIDEO_FACTORY_ASR_API_KEY: str = ""
    VIDEO_FACTORY_ASR_BASE_URL: str = ""
    VIDEO_FACTORY_ASR_MODEL: str = "gpt-4o-mini-transcribe"
    VIDEO_FACTORY_ASR_API_PATH: str = "/audio/transcriptions"
    VIDEO_FACTORY_ASR_TIMEOUT_SECONDS: float = 180.0
    VIDEO_FACTORY_ASR_LANGUAGE: str = "zh"
    VIDEO_FACTORY_ASR_MAX_TEXT_CHARS: int = 500
    VIDEO_FACTORY_REFERENCE_MAX_UPLOAD_MB: int = 256
    BAIQIPU_FFMPEG_BIN: str = "ffmpeg"

    # Optional auto-publish to Xiaohongshu MCP service.
    XHS_AUTOPUBLISH_ENABLED: bool = False
    XHS_MCP_BASE_URL: str = "http://127.0.0.1:18060"
    XHS_MCP_PUBLISH_VIDEO_PATH: str = "/api/v1/publish_video"
    XHS_MCP_AUTO_COMMENT_PATH: str = "/api/v1/comment/create"
    XHS_MCP_FETCH_COMMENTS_PATH: str = "/api/v1/comment/list"
    XHS_MCP_TIMEOUT_SECONDS: float = 180.0
    XHS_COOKIE_PATH: str = ""
    XHS_DEFAULT_VISIBILITY: str = "公开可见"
    XHS_COMMENT_DEFAULT_TEXT: str = "欢迎交流，感谢观看。"
    XHS_COMMENT_DEFAULT_LIMIT: int = 20

    N8N_WEBHOOK_URL: str = ""
    N8N_TIMEOUT_SECONDS: float = 20.0
    N8N_CALLBACK_SHARED_SECRET: str = ""

    # Cross-border integrations
    CROSSBORDER_API_KEY: str = ""
    SHOPEE_API_BASE_URL: str = "https://partner.shopeemobile.com"
    SHOPEE_PARTNER_ID: str = ""
    SHOPEE_PARTNER_KEY: str = ""
    SHOPEE_SHOP_ID_MY: str = ""
    SHOPEE_SHOP_ID_TH: str = ""
    SHOPEE_REDIRECT_URL: str = ""
    SHOPEE_TOKEN_ENCRYPTION_KEY: str = ""
    SHOPEE_DEFAULT_CATEGORY_ID: str = ""
    SHOPEE_DEFAULT_LOGISTIC_ID: str = ""
    SHOPEE_DEFAULT_WEIGHT_KG: float = 0.35
    SHOPEE_LIVE_ITEM_STATUS: str = "UNLIST"
    AMAZON_SELLER_ID: str = ""
    AMAZON_LWA_CLIENT_ID: str = ""
    AMAZON_LWA_CLIENT_SECRET: str = ""
    AMAZON_MARKETPLACE_ID_US: str = ""
    AMAZON_MARKETPLACE_ID_JP: str = ""
    ETSY_API_KEY: str = ""
    ETSY_SHOP_ID: str = ""

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = {"env_file": ".env", "extra": "ignore"}

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production", "false", "0", "no", "off"}:
                return False
            if normalized in {"debug", "dev", "development", "true", "1", "yes", "on", "local"}:
                return True
        return value

    @field_validator("ADMIN_BOOTSTRAP_PHONES", "OPERATOR_BOOTSTRAP_PHONES", mode="before")
    @classmethod
    def normalize_phone_lists(cls, value):
        if value in (None, "", []):
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    parsed = []
                return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
