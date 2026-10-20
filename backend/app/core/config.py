from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="PM_")
    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./data/papermind.db"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str | None = None
    qdrant_api_key: SecretStr | None = None
    storage_path: Path = Path("data")
    secret_key: SecretStr = SecretStr("development-only-change-this-key-before-deploying")
    cors_origins: list[str] = ["http://localhost:3000"]
    task_eager: bool = True
    parser: str = "docling"
    docling_pipeline: str = "standard"
    docling_cell_matching: bool = False
    max_upload_mb: int = 30
    max_pages: int = 150
    max_extraction_sources: int = 20
    token_expiry_minutes: int = 120
    rate_limit_per_minute: int = 120
    bm25_max_documents: int = Field(default=50000, ge=1, le=1000000)
    bm25_max_characters: int = Field(default=32000000, ge=1000)
    bm25_cache_entries: int = Field(default=2, ge=1, le=8)
    base_url: str = "https://api.openai.com/v1"
    api_key: SecretStr | None = None
    chat_model: str = "gpt-4.1-mini"
    embedding_backend: str = "local"
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_api_key: SecretStr | None = None
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    reranker_backend: str = "local"
    reranker_model: str = "cross-encoder/ms-marco-TinyBERT-L2-v2"
    reranker_url: str | None = None
    reranker_api_key: SecretStr | None = None
    temperature: float = 0.0
    context_length: int = 16000
    timeout: float = 90
    retries: int = 2
    max_output_tokens: int = 2500
    agent_max_tools: int = 8
    agent_timeout: int = 180
    max_input_tokens: int = 24000
    max_total_tokens: int = 30000
    max_cost_usd: float = 0.25
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None
    openalex_api_key: SecretStr | None = None
    langfuse_enabled: bool = False

    @model_validator(mode="after")
    def production_guards(self):
        if self.environment == "production":
            if self.secret_key.get_secret_value().startswith(("development", "replace-")):
                raise ValueError("A strong PM_SECRET_KEY is required in production")
            if len(self.secret_key.get_secret_value()) < 32:
                raise ValueError("PM_SECRET_KEY must have at least 32 characters")
            if self.task_eager or not self.database_url.startswith("postgresql") or not self.qdrant_url:
                raise ValueError("Production requires PostgreSQL, remote Qdrant and a separate worker")
        return self


@lru_cache
def settings() -> Settings:
    return Settings()
