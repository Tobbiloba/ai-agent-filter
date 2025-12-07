"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./ai_firewall.db"

    # Security
    secret_key: str = "change-me-in-production"
    api_key_header: str = "X-API-Key"

    # Rate Limiting defaults
    rate_limit_requests: int = 100
    rate_limit_window: int = 3600  # seconds

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
