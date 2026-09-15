from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Values come from environment or ``.env``."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "NeoStore"
    env: str = "local"

    database_url: str = "postgresql+asyncpg://neostore:neostore@db:5432/neostore"
    redis_url: str = "redis://redis:6379/0"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60 * 24

    exchange_rate_api_url: str = "https://open.er-api.com/v6/latest"
    exchange_rate_api_key: str = ""
    exchange_rate_refresh_hours: int = 6

    default_locale: str = "zh-CN"
    default_currency: str = "USD"
    region_cookie_name: str = "neostore_region"
    locale_cookie_name: str = "neostore_locale"
    cart_token_cookie: str = "neostore_cart"

    #: The mock gateway is what makes the demo a closed loop, but it must never
    #: be reachable in production: it lets anyone mark any order paid. Turn it
    #: off the moment a real provider is wired up.
    enable_mock_payments: bool = True

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    seed_admin_email: str = "admin@neostore.local"
    seed_admin_password: str = "admin123"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
