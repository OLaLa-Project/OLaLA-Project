from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    cors_origins: str = ""
    log_dir: str = "/app/logs"
    youtube_query_max_len: int = 80

    ollama_url: str = "http://ollama:11434"
    ollama_timeout: float = 60.0
    embed_model: str = "nomic-embed-text"
    embed_dim: int = 768

    naver_client_id: str = ""
    naver_client_secret: str = ""
    wiki_embeddings_ready: bool = False

    checkpoint_enabled: bool = True
    checkpoint_backend: str = "postgres"
    checkpoint_ttl_seconds: int = 86400
    checkpoint_thread_table: str = "checkpoint_threads"

    external_api_timeout_seconds: float = 10.0
    external_api_retry_attempts: int = 3
    external_api_backoff_seconds: float = 0.4
    naver_max_concurrency: int = 3
    ddg_max_concurrency: int = 3

    slm_base_url: str = "http://localhost:8080/v1"
    slm_api_key: str = "local-slm-key"
    slm_model: str = "slm"
    slm_timeout_seconds: int = 60
    slm_max_tokens: int = 1024
    slm_temperature: float = 0.1

    slm1_base_url: str = "http://localhost:8080/v1"
    slm1_api_key: str = "local-slm-key"
    slm1_model: str = "gemma3:4b"
    slm1_timeout_seconds: int = 60
    slm1_max_tokens: int = 1024
    slm1_temperature: float = 0.1

    slm2_base_url: str = "http://localhost:8080/v1"
    slm2_api_key: str = "local-slm-key"
    slm2_model: str = "gemma3:4b"
    slm2_timeout_seconds: int = 60
    slm2_max_tokens: int = 1024
    slm2_temperature: float = 0.1

    judge_base_url: str = "https://api.openai.com/v1"
    judge_api_key: str = ""
    judge_model: str = "gpt-4.1"
    judge_timeout_seconds: int = 60
    judge_max_tokens: int = 1024
    judge_temperature: float = 0.2

    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "olala"
    db_user: str = "postgres"
    db_password: str = "postgres"
    database_url: str = ""
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_query_timeout: int = 30
    db_pool_pre_ping: bool = True
    db_lock_timeout_seconds: float = 15.0
    db_statement_timeout_seconds: float = 0.0
    db_synchronous_commit: str = "on"
    embed_ndigits: int = 6
    embed_stop_file: str = ""

    @field_validator("ollama_url", mode="before")
    @classmethod
    def _normalize_ollama_url(cls, value: str) -> str:
        return str(value or "http://ollama:11434").strip().rstrip("/")

    @field_validator("checkpoint_backend", mode="before")
    @classmethod
    def _normalize_checkpoint_backend(cls, value: str) -> str:
        backend = str(value or "postgres").strip().lower()
        if backend in {"memory", "postgres", "none"}:
            return backend
        return "postgres"

    @property
    def cors_origins_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        if origins:
            return origins
        return [
            "http://localhost:5175",
            "http://127.0.0.1:5175",
            "http://192.168.0.4:5175",
        ]

    @property
    def database_url_resolved(self) -> str:
        if self.database_url.strip():
            return self.database_url.strip()
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
