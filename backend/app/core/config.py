from functools import lru_cache
from typing import Any

try:  # Pydantic v2
    from pydantic import Field, field_validator
    from pydantic_settings import BaseSettings, SettingsConfigDict
    PYDANTIC_V2 = True
except ImportError:  # Pydantic v1 fallback for local/dev environments
    from pydantic import BaseSettings, Field, validator

    PYDANTIC_V2 = False

    def field_validator(*fields: str, mode: str = "after", **kwargs: Any):
        """Compat shim that maps the Pydantic v2 decorator to v1's validator."""

        pre = mode == "before"

        def decorator(func):
            return validator(*fields, pre=pre, allow_reuse=True, **kwargs)(func)

        return decorator


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env files."""

    if PYDANTIC_V2:
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore",
        )
    else:
        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
            case_sensitive = False
            extra = "ignore"

    app_name: str = Field(default="AI-Driven Energy Supply Chain Resilience")
    app_version: str = Field(default="0.1.0")
    api_v1_prefix: str = Field(default="/api/v1")
    environment: str = Field(default="development")
    debug: bool = Field(default=False)

    secret_key: str = Field(default="change-me-in-production")
    access_token_expire_minutes: int = Field(default=60 * 24)
    algorithm: str = Field(default="HS256")
    rate_limit_enabled: bool = Field(default=False)
    rate_limit_requests_per_minute: int = Field(default=120)
    startup_check_strict: bool = Field(default=True)

    database_url: str = Field(default="sqlite:///./energy_resilience.db")
    redis_url: str = Field(default="redis://localhost:6379/0")
    enable_scheduler: bool = Field(default=False)
    scheduler_interval_minutes: int = Field(default=30)
    demo_mode: bool = Field(default=True)

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5500",
            "http://127.0.0.1:5500",
        ],
        env="BACKEND_CORS_ORIGINS",
    )

    log_level: str = Field(default="INFO")
    docs_url: str = Field(default="/docs")
    redoc_url: str = Field(default="/redoc")
    openapi_url: str = Field(default="/openapi.json")

    llm_provider: str = Field(default="gemini")
    llm_model: str = Field(default="gpt-4o-mini")
    gemini_api_key: str = Field(default="")
    gemini_base_url: str = Field(default="https://generativelanguage.googleapis.com/v1beta")
    gemini_model: str = Field(default="gemini-1.5-flash")
    groq_api_key: str = Field(default="")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1")

    gdelt_enabled: bool = Field(default=True)
    gdelt_base_url: str = Field(default="https://api.gdeltproject.org/api/v2")
    newsapi_enabled: bool = Field(default=False)
    newsapi_api_key: str = Field(default="")
    newsapi_base_url: str = Field(default="https://newsapi.org/v2")
    event_registry_enabled: bool = Field(default=False)
    event_registry_api_key: str = Field(default="")

    ofac_enabled: bool = Field(default=True)
    ofac_base_url: str = Field(default="https://sanctionssearch.ofac.treas.gov")
    uk_sanctions_enabled: bool = Field(default=False)
    eu_sanctions_enabled: bool = Field(default=False)
    un_sanctions_enabled: bool = Field(default=False)

    ais_provider: str = Field(default="mock")
    marinetraffic_api_key: str = Field(default="")
    marinetraffic_base_url: str = Field(default="https://services.marinetraffic.com/api")
    vesselfinder_api_key: str = Field(default="")
    vesselfinder_base_url: str = Field(default="https://api.vesselfinder.com")
    datalastic_api_key: str = Field(default="")
    datalastic_base_url: str = Field(default="https://api.datalastic.com/api/v0")

    price_provider: str = Field(default="mock")
    alphavantage_api_key: str = Field(default="")
    alphavantage_base_url: str = Field(default="https://www.alphavantage.co/query")
    eia_api_key: str = Field(default="")
    eia_base_url: str = Field(default="https://api.eia.gov/v2")
    crudeprice_api_key: str = Field(default="")
    crudeprice_base_url: str = Field(default="https://www.crudepriceapi.com/api")

    @field_validator("cors_origins", mode="before")
    def parse_cors_origins(cls, value: Any) -> list[str]:
        """Allow comma-separated strings from environment variables."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            raw_values = [item.strip() for item in value.split(",")]
            return [item for item in raw_values if item]
        raise TypeError("cors_origins must be a list or comma-separated string")

    @field_validator("enable_scheduler", mode="before")
    def parse_enable_scheduler(cls, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @field_validator(
        "debug",
        "demo_mode",
        "gdelt_enabled",
        "newsapi_enabled",
        "event_registry_enabled",
        "ofac_enabled",
        "uk_sanctions_enabled",
        "eu_sanctions_enabled",
        "un_sanctions_enabled",
        mode="before",
    )
    def parse_flags(cls, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @field_validator("environment", mode="before")
    def normalize_environment(cls, value: Any) -> str:
        environment = str(value or "development").strip().lower()
        allowed = {"development", "staging", "production"}
        if environment not in allowed:
            raise ValueError(f"environment must be one of: {', '.join(sorted(allowed))}")
        return environment

    @field_validator("secret_key", mode="before")
    def normalize_secret_key(cls, value: Any) -> str:
        secret_key = str(value or "").strip()
        if not secret_key:
            raise ValueError("secret_key must not be empty")
        return secret_key

    @field_validator("rate_limit_requests_per_minute", mode="before")
    def normalize_rate_limit(cls, value: Any) -> int:
        if value is None or value == "":
            return 120
        return max(1, int(value))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance for dependency reuse."""
    return Settings()


settings = get_settings()
