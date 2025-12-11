"""Database configuration and session management."""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from server.config import get_settings

settings = get_settings()


def _is_sqlite(url: str) -> bool:
    """Check if database URL is SQLite."""
    return url.startswith("sqlite")


def _is_pooler_url(url: str) -> bool:
    """Check if database URL uses a connection pooler (e.g., Neon's PgBouncer)."""
    return "-pooler" in url or "pgbouncer" in url.lower()


def _fix_asyncpg_ssl(url: str) -> str:
    """Fix SSL parameter for asyncpg compatibility.

    asyncpg uses 'ssl' parameter, not 'sslmode' (which is for psycopg2/libpq).
    For Neon and other cloud PostgreSQL providers, ssl=true works best.
    """
    if "asyncpg" in url:
        # Replace sslmode=X with ssl=true (most compatible format for asyncpg)
        if "sslmode=" in url:
            # Remove sslmode parameter and add ssl=true
            import re
            url = re.sub(r'[?&]sslmode=[^&]*', '', url)
            # Add ssl=true
            if "?" in url:
                url += "&ssl=true"
            else:
                url += "?ssl=true"
        # Also handle if ssl=require was set (convert to ssl=true)
        elif "ssl=require" in url:
            url = url.replace("ssl=require", "ssl=true")
    return url


def create_engine_with_config():
    """Create async engine with appropriate config for database type."""
    # Fix sslmode for asyncpg compatibility
    database_url = _fix_asyncpg_ssl(settings.database_url)
    is_sqlite = _is_sqlite(database_url)

    if is_sqlite:
        # SQLite: No connection pooling, use NullPool for async compatibility
        return create_async_engine(
            database_url,
            echo=settings.db_echo or settings.debug,
            future=True,
            poolclass=NullPool,
        )
    else:
        # PostgreSQL: Full connection pooling
        # Check if using a connection pooler (Neon, Supabase, etc.)
        connect_args = {}
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

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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
