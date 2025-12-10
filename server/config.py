"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Logging
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_json: bool = True  # JSON format for production, False for human-readable

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

    # Redis Configuration (Optional - leave empty to disable)
    redis_url: str = ""  # e.g., "redis://localhost:6379/0"
    redis_pool_size: int = 10
    redis_timeout: float = 1.0  # seconds
    cache_ttl_policy: int = 300  # 5 minutes
    cache_ttl_project: int = 600  # 10 minutes
    cache_enabled: bool = True  # Master switch for caching

    # Fail-Closed Mode
    fail_closed: bool = False  # If True, block actions when service errors occur
    fail_closed_reason: str = "Service unavailable - fail-closed mode active"

    # Graceful Shutdown
    shutdown_timeout: int = 30  # Seconds to wait for in-flight requests to drain

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
