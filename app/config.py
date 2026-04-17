from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from datetime import datetime
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # DB
    database_url: str = Field(alias="DATABASE_URL")

    # Redis/Celery
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")
    celery_broker_url: str = Field(default="redis://redis:6379/0", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://redis:6379/0", alias="CELERY_RESULT_BACKEND")

    # Telegram
    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    telegram_channel: str = Field(alias="TELEGRAM_CHANNEL")
    telegram_admin_ids: str = Field(default="", alias="TELEGRAM_ADMIN_IDS")  # comma-separated
    telegram_proxy_url: str = Field(default="", alias="TELEGRAM_PROXY_URL")  # socks5://user:pass@host:port or http://

    # AI
    ai_provider: str = Field(default="openai", alias="AI_PROVIDER")
    ai_api_key: str = Field(default="", alias="AI_API_KEY")
    ai_base_url: str = Field(default="https://api.openai.com/v1", alias="AI_BASE_URL")
    # Backward compatibility with legacy polza.ai variable names
    polza_api_key: str = Field(default="", alias="POLZA_API_KEY")
    polza_base_url: str = Field(default="", alias="POLZA_BASE_URL")
    ai_model: str = Field(default="gpt-4o-mini", alias="AI_MODEL")
    ai_temperature: float = Field(default=0.4, alias="AI_TEMPERATURE")
    tg_translation_model: str = Field(default="gpt-4o-mini", alias="TG_TRANSLATION_MODEL")
    tg_translation_style: str = Field(default="neutral", alias="TG_TRANSLATION_STYLE")  # formal|neutral|social
    tg_publish_language: str = Field(default="th", alias="TG_PUBLISH_LANGUAGE")  # th|ru|en|es|it

    # Cutoffs
    # If set, collectors will skip items older than N days (sliding window)
    news_not_before_days: Optional[int] = Field(default=None, alias="NEWS_NOT_BEFORE_DAYS")
    # If set, AI summarizer will skip items older than N days (sliding window)
    ai_not_before_days: Optional[int] = Field(default=None, alias="AI_NOT_BEFORE_DAYS")
    # Optional absolute cutoff (ISO date/datetime). If provided, used only when *_DAYS is not set.
    news_not_before: Optional[datetime] = Field(default=None, alias="NEWS_NOT_BEFORE")
    ai_not_before: Optional[datetime] = Field(default=None, alias="AI_NOT_BEFORE")

    # App
    app_env: str = Field(default="prod", alias="APP_ENV")
    app_base_url: str = Field(default="http://localhost:8000", alias="APP_BASE_URL")
    secret_key: str = Field(default="change_me", alias="SECRET_KEY")
    web_password: str = Field(default="", alias="WEB_PASSWORD")

    auto_disable_on_401_403: bool = Field(default=False, alias="AUTO_DISABLE_ON_401_403")
    auto_disable_threshold: int = Field(default=3, alias="AUTO_DISABLE_THRESHOLD")

    @property
    def telegram_admin_id_set(self) -> set[int]:
        s = (self.telegram_admin_ids or "").strip()
        if not s:
            return set()
        out = set()
        for part in s.split(","):
            part = part.strip()
            if part:
                out.add(int(part))
        return out

    @property
    def telegram_proxy(self) -> str | None:
        value = (self.telegram_proxy_url or "").strip()
        if not value:
            return None
        return value

    @property
    def effective_ai_api_key(self) -> str:
        return (self.ai_api_key or self.polza_api_key or "").strip()

    @property
    def effective_ai_base_url(self) -> str:
        if (self.ai_base_url or "").strip():
            return self.ai_base_url.strip()
        if (self.polza_base_url or "").strip():
            return self.polza_base_url.strip()
        return "https://api.openai.com/v1"

settings = Settings()
