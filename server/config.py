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

    # PostgreSQL Connection Pool Settings (ignored for SQLite)
    db_pool_size: int = 5  # Base number of connections in pool
    db_max_overflow: int = 10  # Extra connections allowed beyond pool_size
    db_pool_timeout: int = 30  # Seconds to wait for a connection
    db_pool_recycle: int = 1800  # Recycle connections after 30 minutes
    db_echo: bool = False  # SQL query logging (separate from debug)

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
