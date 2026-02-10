import json
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "olala-fastapi"
    environment: str = "local"
    api_prefix: str = "/v1"

    database_url: str = (
        "postgresql+asyncpg://olala:olala@postgres:5432/olala"
    )
    redis_url: str = "redis://redis:6379/0"
    redis_channel: str = "olala:chat:events"

    cors_origins: str = "*"
    log_level: str = "INFO"

    issue_timezone: str = "Asia/Seoul"
    default_issue_category: str = "정치"
    max_chat_history_limit: int = 200
    max_message_length: int = 500

    verify_provider: str = "auto"
    verify_search_limit: int = 5
    verify_request_timeout_seconds: int = 20
    verify_search_api_url: str = "https://api.duckduckgo.com/"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_verify_model: str = "gpt-4o-mini"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _normalize_cors_origins(cls, value: object) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            return ",".join(str(item).strip() for item in value if str(item).strip())
        return "*"

    @property
    def cors_origins_list(self) -> list[str]:
        raw = (self.cors_origins or "").strip()
        if not raw or raw == "*":
            return ["*"]

        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    origins = [str(item).strip() for item in parsed if str(item).strip()]
                    return origins or ["*"]
            except json.JSONDecodeError:
                pass

        origins = [item.strip() for item in raw.split(",") if item.strip()]
        return origins or ["*"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
