"""Centralized application configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Spider"
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = True
    secret_key: str = "change-me-to-a-long-random-string"
    encryption_key: str = "change-me-32-byte-base64-or-fernet-key"

    # Backend
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_cors_origins: str = "http://localhost:3000"

    # Database
    database_url: str = "postgresql+asyncpg://spider:spider@localhost:5432/spider"
    database_url_sync: str = "postgresql://spider:spider@localhost:5432/spider"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # GitHub App
    github_app_id: str = ""
    github_app_client_id: str = ""
    github_app_client_secret: str = ""
    github_app_private_key_path: str = "./secrets/github-app.pem"
    github_app_webhook_secret: str = ""
    github_app_name: str = ""

    # Gemini (centralized — never hardcode model names elsewhere)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_embedding_model: str = "text-embedding-004"
    gemini_temperature: float = 0.1
    gemini_max_output_tokens: int = 8192
    gemini_embedding_dimensions: int = 768

    # Review defaults
    review_auto_enabled: bool = True
    review_max_files: int = 50
    review_context_limit: int = 20
    review_severity_threshold: str = "medium"
    monthly_budget_usd: float = 100.0
    review_confidence_threshold: float = 0.6

    # Sandbox
    sandbox_image: str = "spider-sandbox:latest"
    sandbox_timeout_seconds: int = 300
    sandbox_memory_limit: str = "512m"
    sandbox_cpu_limit: float = 1.0

    # Storage
    repos_base_path: str = "/data/repos"

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def _normalize_cors(cls, value: str | list[str]) -> str:
        if isinstance(value, list):
            return ",".join(value)
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def github_app_configured(self) -> bool:
        return bool(self.github_app_id and self.github_app_webhook_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()