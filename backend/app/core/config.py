from functools import lru_cache
from typing import Any

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env files."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="AI-Driven Energy Supply Chain Resilience")
    app_version: str = Field(default="0.1.0")
    api_v1_prefix: str = Field(default="/api/v1")
    environment: str = Field(default="development")
    debug: bool = Field(default=False)

    secret_key: str = Field(default="change-me-in-production")
    access_token_expire_minutes: int = Field(default=60 * 24)
    algorithm: str = Field(default="HS256")

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/energy_resilience"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")

    cors_origins: list[str] = Field(
        validation_alias=AliasChoices("BACKEND_CORS_ORIGINS", "CORS_ORIGINS"),
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5500",
            "http://127.0.0.1:5500",
        ]
    )

    log_level: str = Field(default="INFO")
    docs_url: str = Field(default="/docs")
    redoc_url: str = Field(default="/redoc")
    openapi_url: str = Field(default="/openapi.json")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        """Allow comma-separated strings or JSON arrays from environment variables."""
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
