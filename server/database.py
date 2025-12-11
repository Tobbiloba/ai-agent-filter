"""Database configuration and session management."""

import re
import ssl

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from server.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


def _is_sqlite(url: str) -> bool:
    """Check if database URL is SQLite."""
    return url.startswith("sqlite")


def _is_pooler_url(url: str) -> bool:
    """Check if database URL uses a connection pooler (e.g., Neon's PgBouncer)."""
    return "-pooler" in url or "pgbouncer" in url.lower()


def _needs_ssl(url: str) -> bool:
    """Check if URL requires SSL (has sslmode or ssl parameter)."""
    return "sslmode=" in url or "ssl=" in url


def _strip_ssl_params(url: str) -> str:
    """Remove sslmode and ssl parameters from URL.

    SQLAlchemy's asyncpg dialect doesn't handle SSL params in the URL.
    Instead, SSL must be passed via connect_args.
    """
    # Remove sslmode=X
    url = re.sub(r'[?&]sslmode=[^&]*', '', url)
    # Remove ssl=X
    url = re.sub(r'[?&]ssl=[^&]*', '', url)
    # Clean up dangling ? or &
    url = re.sub(r'\?&', '?', url)
    url = re.sub(r'\?$', '', url)
    return url


def create_engine_with_config():
    """Create async engine with appropriate config for database type."""
    original_url = settings.database_url
    is_sqlite = _is_sqlite(original_url)

    if is_sqlite:
        # SQLite: No connection pooling, use NullPool for async compatibility
        return create_async_engine(
            original_url,
            echo=settings.db_echo or settings.debug,
            future=True,
            poolclass=NullPool,
        )
    else:
        # PostgreSQL: Handle SSL and connection pooling
        connect_args = {}

        # For asyncpg, SSL must be passed via connect_args, not URL
        if "asyncpg" in original_url and _needs_ssl(original_url):
            # Strip SSL params from URL and pass via connect_args
            database_url = _strip_ssl_params(original_url)
            connect_args["ssl"] = ssl.create_default_context()
        else:
            database_url = original_url

        # Check if using a connection pooler (Neon, Supabase, etc.)
        if _is_pooler_url(database_url):
            # Disable prepared statements for PgBouncer compatibility
            connect_args["prepared_statement_cache_size"] = 0

        return create_async_engine(
            database_url,
            echo=settings.db_echo or settings.debug,
            future=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
            pool_pre_ping=True,  # Verify connections before use
            connect_args=connect_args,
        )


engine = create_engine_with_config()

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


async def get_db() -> AsyncSession:
    """Dependency for getting database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    # Import models to register them with SQLAlchemy
    from server.models import Project, Policy, AuditLog  # noqa: F401

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized successfully")
    except Exception as e:
        # Log error but don't crash - app can still serve health checks
        logger.error(f"Failed to initialize database tables: {e}", exc_info=True)
        logger.warning("App will continue but database operations may fail until connection is established")


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()


def get_database_type() -> str:
    """Return the database type for health checks."""
    if "postgresql" in settings.database_url:
        return "postgresql"
    elif "sqlite" in settings.database_url:
        return "sqlite"
    return "unknown"
