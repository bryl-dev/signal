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
