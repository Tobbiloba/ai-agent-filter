"""
Integration tests for PostgreSQL database support.

These tests require a running PostgreSQL instance.
Set TEST_POSTGRES_URL environment variable to run these tests.

Example:
    docker run -d --name test-pg \
        -e POSTGRES_USER=test \
        -e POSTGRES_PASSWORD=test \
        -e POSTGRES_DB=ai_firewall_test \
        -p 5433:5432 \
        postgres:16-alpine

    TEST_POSTGRES_URL="postgresql+asyncpg://test:test@localhost:5433/ai_firewall_test" \
        pytest tests/integration/test_postgresql.py -v
"""

import os
import asyncio
import pytest
from typing import Generator

# Skip all tests if PostgreSQL URL not provided
pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_POSTGRES_URL"),
    reason="TEST_POSTGRES_URL not set - skipping PostgreSQL tests"
)


@pytest.fixture(scope="module")
def postgres_url() -> str:
    """Get PostgreSQL URL from environment."""
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL not set")
    return url


@pytest.fixture(scope="module")
def postgres_engine(postgres_url):
    """Create PostgreSQL engine for testing."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(
        postgres_url,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    yield engine

    # Cleanup
    asyncio.get_event_loop().run_until_complete(engine.dispose())


@pytest.fixture(scope="module")
def postgres_tables(postgres_engine):
    """Create tables in PostgreSQL."""
    from server.database import Base
    from server.models import Project, Policy, AuditLog  # noqa: F401

    async def setup():
        async with postgres_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def teardown():
        async with postgres_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    asyncio.get_event_loop().run_until_complete(setup())
    yield
    asyncio.get_event_loop().run_until_complete(teardown())


class TestPostgreSQLConnection:
    """Test basic PostgreSQL connectivity."""

    @pytest.mark.asyncio
    async def test_connect_to_postgres(self, postgres_engine):
        """Can establish connection to PostgreSQL."""
        from sqlalchemy import text

        async with postgres_engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            row = result.fetchone()
            assert row[0] == 1

    @pytest.mark.asyncio
    async def test_create_tables(self, postgres_engine, postgres_tables):
        """init_db() creates all tables in PostgreSQL."""
        from sqlalchemy import text

        async with postgres_engine.connect() as conn:
            # Check projects table exists
            result = await conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_name = 'projects'")
            )
            assert result.fetchone() is not None

            # Check policies table exists
            result = await conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_name = 'policies'")
            )
            assert result.fetchone() is not None

            # Check audit_logs table exists
            result = await conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_name = 'audit_logs'")
            )
            assert result.fetchone() is not None


class TestPostgreSQLCRUD:
    """Test CRUD operations on PostgreSQL."""

    @pytest.mark.asyncio
    async def test_create_project(self, postgres_engine, postgres_tables):
        """Create project works in PostgreSQL."""
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        from server.models import Project

        async_session = async_sessionmaker(
            postgres_engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session() as session:
            project = Project(id="test-pg-project", name="PostgreSQL Test Project")
            session.add(project)
            await session.commit()

            assert project.api_key is not None
            assert project.api_key.startswith("af_")

            # Cleanup
            await session.delete(project)
            await session.commit()

    @pytest.mark.asyncio
    async def test_create_policy(self, postgres_engine, postgres_tables):
        """Create policy works in PostgreSQL."""
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        from server.models import Project, Policy
        import json

        async_session = async_sessionmaker(
            postgres_engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session() as session:
            # Create project first
            project = Project(id="test-pg-policy-project", name="Policy Test Project")
            session.add(project)
            await session.flush()

            # Create policy
            policy = Policy(
                project_id=project.id,
                name="test-policy",
                version="1.0",
                rules=json.dumps({"default": "allow", "rules": []}),
            )
            session.add(policy)
            await session.commit()

            assert policy.id is not None

            # Cleanup
            await session.delete(policy)
            await session.delete(project)
            await session.commit()

    @pytest.mark.asyncio
    async def test_create_audit_log(self, postgres_engine, postgres_tables):
        """Create audit log works in PostgreSQL."""
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        from server.models import Project, AuditLog
        import json

        async_session = async_sessionmaker(
            postgres_engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session() as session:
            # Create project first
            project = Project(id="test-pg-log-project", name="Log Test Project")
            session.add(project)
            await session.flush()

            # Create audit log
            log = AuditLog(
                project_id=project.id,
                agent_name="test-agent",
                action_type="test_action",
                params=json.dumps({"key": "value"}),
                allowed=True,
            )
            session.add(log)
            await session.commit()

            assert log.action_id is not None
            assert log.action_id.startswith("act_")

            # Cleanup
            await session.delete(log)
            await session.delete(project)
            await session.commit()


class TestPostgreSQLConstraints:
    """Test database constraints in PostgreSQL."""

    @pytest.mark.asyncio
    async def test_foreign_key_cascade(self, postgres_engine, postgres_tables):
        """Deleting project cascades to policies and logs."""
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        from sqlalchemy import select
        from server.models import Project, Policy, AuditLog
        import json

        async_session = async_sessionmaker(
            postgres_engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session() as session:
            # Create project with policy and log
            project = Project(id="test-cascade-project", name="Cascade Test")
            session.add(project)
            await session.flush()

            policy = Policy(
                project_id=project.id,
                name="cascade-policy",
                version="1.0",
                rules=json.dumps({"default": "allow", "rules": []}),
            )
            log = AuditLog(
                project_id=project.id,
                agent_name="cascade-agent",
                action_type="cascade_action",
                params=json.dumps({}),
                allowed=True,
            )
            session.add(policy)
            session.add(log)
            await session.commit()

            policy_id = policy.id
            log_id = log.id

            # Delete project
            await session.delete(project)
            await session.commit()

            # Verify cascaded deletes
            result = await session.execute(select(Policy).where(Policy.id == policy_id))
            assert result.scalar_one_or_none() is None

            result = await session.execute(select(AuditLog).where(AuditLog.id == log_id))
            assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_unique_api_key_constraint(self, postgres_engine, postgres_tables):
        """API key uniqueness is enforced."""
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        from sqlalchemy.exc import IntegrityError
        from server.models import Project

        async_session = async_sessionmaker(
            postgres_engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session() as session:
            # Create first project
            project1 = Project(id="unique-test-1", name="Unique Test 1")
            session.add(project1)
            await session.flush()
            api_key = project1.api_key

            # Try to create second project with same API key
            project2 = Project(id="unique-test-2", name="Unique Test 2")
            project2.api_key = api_key  # Force same API key
            session.add(project2)

            with pytest.raises(IntegrityError):
                await session.commit()

            await session.rollback()

            # Cleanup
            await session.delete(project1)
            await session.commit()


class TestPostgreSQLConcurrency:
    """Test concurrent operations in PostgreSQL."""

    @pytest.mark.asyncio
    async def test_concurrent_writes(self, postgres_engine, postgres_tables):
        """10 concurrent inserts succeed without conflicts."""
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        from server.models import Project

        async_session = async_sessionmaker(
            postgres_engine, class_=AsyncSession, expire_on_commit=False
        )

        async def create_project(i: int):
            async with async_session() as session:
                project = Project(id=f"concurrent-{i}", name=f"Concurrent Test {i}")
                session.add(project)
                await session.commit()
                return project.id

        # Create 10 projects concurrently
        tasks = [create_project(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert len(set(results)) == 10  # All unique

        # Cleanup
        async with async_session() as session:
            for i in range(10):
                project = await session.get(Project, f"concurrent-{i}")
                if project:
                    await session.delete(project)
            await session.commit()

    @pytest.mark.asyncio
    async def test_connection_pool_under_load(self, postgres_engine, postgres_tables):
        """50 concurrent requests don't exhaust connection pool."""
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        from sqlalchemy import text

        async_session = async_sessionmaker(
            postgres_engine, class_=AsyncSession, expire_on_commit=False
        )

        async def run_query(i: int):
            async with async_session() as session:
                result = await session.execute(text("SELECT pg_sleep(0.01), :i"), {"i": i})
                return i

        # Run 50 concurrent queries
        tasks = [run_query(i) for i in range(50)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 50
        assert set(results) == set(range(50))


class TestPostgreSQLPoolPrePing:
    """Test pool_pre_ping functionality."""

    @pytest.mark.asyncio
    async def test_pool_pre_ping_enabled(self, postgres_engine):
        """Verify pool_pre_ping is enabled."""
        # pool_pre_ping should be True
        assert postgres_engine.pool._pre_ping is True
