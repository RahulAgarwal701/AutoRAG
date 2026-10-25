from functools import lru_cache
from typing import Annotated

from pydantic import BeforeValidator, SecretStr
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _parse_origins(value: object) -> list[str]:
    if isinstance(value, str):
        return [origin.strip() for origin in value.split(",") if origin.strip()]
    if isinstance(value, list):
        return [str(origin) for origin in value]
    raise ValueError("CORS_ORIGINS must be a comma-separated string or list")


CorsOrigins = Annotated[list[str], NoDecode, BeforeValidator(_parse_origins)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "AutoRAG API"
    app_env: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    cors_origins: CorsOrigins = ["http://localhost:3000"]
    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    widget_session_token_expire_minutes: int = 30
    api_key_rate_limit: int = 60
    ip_rate_limit: int = 120
    widget_session_ip_rate_limit: int = 30
    rate_limit_window_seconds: int = 60

    database_url: str = "postgresql+asyncpg://autorag:autorag@localhost:5432/autorag"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection_name: str = "autorag_chunks"

    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "autorag-ingestion"
    run_temporal_worker_in_process: bool = False

    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-1"
    s3_bucket: str = "autorag-documents"
    s3_endpoint_url: str | None = None
    s3_public_endpoint_url: str | None = None
    max_upload_size_mb: int = 25
    s3_presigned_url_expiry_seconds: int = 900

    gemini_api_key: SecretStr | None = None
    embedding_model: str = "gemini-embedding-001"
    embedding_dimension: int = 1536
    embedding_batch_size: int = 64
    sparse_embedding_provider: str = "bm25"
    query_rewrite_model: str = "gemini-2.5-flash-lite"
    cohere_api_key: SecretStr | None = None
    cohere_rerank_model: str = "rerank-v3.5"
    retrieval_relevance_threshold: float = 0.2

    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    xai_api_key: SecretStr | None = None
    xai_base_url: str = "https://api.x.ai/v1"
    web_search_url: str | None = None
    web_search_api_key: SecretStr | None = None
    tool_webhook_allowed_hosts: CorsOrigins = []

    sentry_dsn: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()

