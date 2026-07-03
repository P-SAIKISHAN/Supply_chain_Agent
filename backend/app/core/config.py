from functools import lru_cache
from typing import Any

from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env files."""

    app_name: str = Field(default="AI-Driven Energy Supply Chain Resilience")
    app_version: str = Field(default="0.1.0")
    api_v1_prefix: str = Field(default="/api/v1")
    environment: str = Field(default="development")
    debug: bool = Field(default=False)

    secret_key: str = Field(default="change-me-in-production")
    access_token_expire_minutes: int = Field(default=60 * 24)
    algorithm: str = Field(default="HS256")

    database_url: str = Field(default="sqlite:///./energy_resilience.db")
    redis_url: str = Field(default="redis://localhost:6379/0")

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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"

    @validator("cors_origins", pre=True)
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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance for dependency reuse."""
    return Settings()


settings = get_settings()
