"""Unit tests for database configuration and setup."""

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.pool import NullPool


class TestDatabaseUrlDetection:
    """Tests for _is_sqlite function."""

    def test_sqlite_url_detected(self):
        """Verify SQLite URLs are correctly identified."""
        from server.database import _is_sqlite

        assert _is_sqlite("sqlite:///./test.db") is True
        assert _is_sqlite("sqlite+aiosqlite:///./test.db") is True
        assert _is_sqlite("sqlite:///:memory:") is True

    def test_postgresql_url_detected(self):
        """Verify PostgreSQL URLs are correctly identified as not SQLite."""
        from server.database import _is_sqlite

        assert _is_sqlite("postgresql://user:pass@localhost/db") is False
        assert _is_sqlite("postgresql+asyncpg://user:pass@localhost/db") is False
        assert _is_sqlite("postgres://user:pass@localhost/db") is False

    def test_other_databases_not_sqlite(self):
        """Verify other database URLs are not identified as SQLite."""
        from server.database import _is_sqlite

        assert _is_sqlite("mysql://user:pass@localhost/db") is False
        assert _is_sqlite("oracle://user:pass@localhost/db") is False


class TestGetDatabaseType:
    """Tests for get_database_type function."""

    def test_returns_sqlite_for_sqlite_url(self):
        """Returns 'sqlite' for SQLite database URLs with default config."""
        from server.database import get_database_type
        from server.config import get_settings

        settings = get_settings()
        # Default config is SQLite
        if "sqlite" in settings.database_url:
            result = get_database_type()
            assert result == "sqlite"

    def test_get_database_type_function_exists(self):
        """get_database_type function exists and is callable."""
        from server.database import get_database_type

        assert callable(get_database_type)
        result = get_database_type()
        assert result in ["sqlite", "postgresql", "unknown"]


class TestDefaultPoolSettings:
    """Tests for default pool configuration values."""

    def test_default_pool_size(self):
        """Default pool size should be 5."""
        from server.config import Settings

        settings = Settings()
        assert settings.db_pool_size == 5

    def test_default_max_overflow(self):
        """Default max overflow should be 10."""
        from server.config import Settings

        settings = Settings()
        assert settings.db_max_overflow == 10

    def test_default_pool_timeout(self):
        """Default pool timeout should be 30 seconds."""
        from server.config import Settings

        settings = Settings()
        assert settings.db_pool_timeout == 30

    def test_default_pool_recycle(self):
        """Default pool recycle should be 1800 seconds (30 min)."""
        from server.config import Settings

        settings = Settings()
        assert settings.db_pool_recycle == 1800

    def test_default_db_echo(self):
        """Default db_echo should be False."""
        from server.config import Settings

        settings = Settings()
        assert settings.db_echo is False


class TestHealthEndpointDatabaseType:
    """Tests for health endpoint including database type."""

    def test_health_returns_database_type(self):
        """Health endpoint should include database type."""
        from fastapi.testclient import TestClient
        from server.app import app

        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert "database" in data
            assert data["database"] in ["sqlite", "postgresql", "unknown"]

    def test_health_returns_sqlite_by_default(self):
        """Health endpoint should return 'sqlite' with default config."""
        from fastapi.testclient import TestClient
        from server.app import app

        with TestClient(app) as client:
            response = client.get("/health")
            data = response.json()
            # Default is SQLite
            assert data["database"] == "sqlite"


class TestEngineConfiguration:
    """Tests for engine configuration based on database type."""

    def test_sqlite_engine_has_null_pool(self):
        """SQLite should use NullPool."""
        from server.database import engine, _is_sqlite
        from server.config import get_settings

        settings = get_settings()
        if _is_sqlite(settings.database_url):
            # SQLite engine should use NullPool
            assert engine.pool.__class__.__name__ == "NullPool"

    def test_engine_created_successfully(self):
        """Engine should be created without errors."""
        from server.database import engine

        assert engine is not None

    def test_session_maker_created_successfully(self):
        """Session maker should be created without errors."""
        from server.database import async_session_maker

        assert async_session_maker is not None
