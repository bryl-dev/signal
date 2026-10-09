from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Signal"
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://signal:signal@localhost:5432/signal"
    database_url_sync: str = "postgresql+psycopg2://signal:signal@localhost:5432/signal"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "dev-only-change-me-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 60 * 60
    refresh_token_ttl_seconds: int = 7 * 24 * 60 * 60

    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    access_cookie_name: str = "access_token"
    refresh_cookie_name: str = "refresh_token"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    login_rate_limit: int = 10
    login_rate_window_seconds: int = 60

    min_interests: int = 5
    ingest_tls_verify: bool = True

    # "fastembed" (local ONNX model) or "hashing" (offline, test-only quality).
    embedding_provider: str = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    # Tuned with `python -m app.clustering.eval`; re-run it when the model or pair set changes.
    cluster_similarity_threshold: float = 0.86
    cluster_window_hours: int = 72
    dedup_min_content_chars: int = 200

    # Feed ranking. Tune relevance with `python -m app.ranking.eval`.
    relevance_similarity_threshold: float = 0.64
    feed_window_days: int = 7
    recency_half_life_hours: float = 24.0
    rank_weight_relevance: float = 0.55
    rank_weight_recency: float = 0.25
    rank_weight_coverage: float = 0.12
    rank_weight_quality: float = 0.08

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
