"""
Integration tests for Redis caching.

These tests require a running Redis instance.
Set TEST_REDIS_URL environment variable to run these tests.

Example:
    docker run -d --name test-redis -p 6379:6379 redis:7-alpine

    TEST_REDIS_URL="redis://localhost:6379/0" \
        pytest tests/integration/test_redis.py -v
"""

import os
import asyncio
import pytest
import pytest_asyncio
import json

# Skip all tests if Redis URL not provided
pytestmark = [
    pytest.mark.skipif(
        not os.getenv("TEST_REDIS_URL"),
        reason="TEST_REDIS_URL not set - skipping Redis tests"
    ),
]


@pytest.fixture(scope="function")
def redis_url() -> str:
    """Get Redis URL from environment."""
    url = os.getenv("TEST_REDIS_URL")
    if not url:
        pytest.skip("TEST_REDIS_URL not set")
    return url


@pytest_asyncio.fixture(scope="function")
async def redis_client(redis_url):
    """Create Redis client for testing."""
    from redis import asyncio as aioredis

    client = aioredis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    yield client

    # Cleanup - flush test keys
    keys = await client.keys("test:*")
    if keys:
        await client.delete(*keys)
    keys = await client.keys("policy:*")
    if keys:
        await client.delete(*keys)
    keys = await client.keys("api_key:*")
    if keys:
        await client.delete(*keys)

    await client.aclose()


@pytest_asyncio.fixture(scope="function")
async def cache_service(redis_client):
    """Create CacheService with test Redis client."""
    from server.cache import CacheService

    service = CacheService(redis_client)
    yield service


class TestRedisConnection:
    """Test basic Redis connectivity."""

    @pytest.mark.asyncio
    async def test_redis_ping(self, redis_client):
        """Can ping Redis server."""
        result = await redis_client.ping()
        assert result is True

    @pytest.mark.asyncio
    async def test_set_and_get(self, redis_client):
        """Basic set and get operations work."""
        await redis_client.set("test:basic", "hello")
        result = await redis_client.get("test:basic")
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_setex_with_ttl(self, redis_client):
        """Set with expiration works."""
        await redis_client.setex("test:ttl", 1, "expires")
        result = await redis_client.get("test:ttl")
        assert result == "expires"

        # Wait for expiration
        await asyncio.sleep(1.5)
        result = await redis_client.get("test:ttl")
        assert result is None


class TestCacheServiceWithRedis:
    """Test CacheService with real Redis."""

    @pytest.mark.asyncio
    async def test_cache_is_available(self, cache_service):
        """Cache reports as available with Redis connection."""
        assert cache_service.is_available is True

    @pytest.mark.asyncio
    async def test_set_and_get_policy(self, cache_service):
        """set_policy and get_policy work correctly."""
        policy_data = {
            "id": 1,
            "project_id": "test-project",
            "name": "default",
            "version": "1.0",
            "rules": '{"default": "allow", "rules": []}',
            "is_active": True,
        }

        result = await cache_service.set_policy("test-project", policy_data)
        assert result is True

        cached = await cache_service.get_policy("test-project")
        assert cached == policy_data

    @pytest.mark.asyncio
    async def test_invalidate_policy(self, cache_service):
        """invalidate_policy removes cached policy."""
        policy_data = {"id": 1, "name": "test"}
        await cache_service.set_policy("invalidate-test", policy_data)

        # Verify it's cached
        cached = await cache_service.get_policy("invalidate-test")
        assert cached is not None

        # Invalidate
        result = await cache_service.invalidate_policy("invalidate-test")
        assert result is True

        # Verify it's gone
        cached = await cache_service.get_policy("invalidate-test")
        assert cached is None

    @pytest.mark.asyncio
    async def test_set_and_get_project_by_api_key(self, cache_service):
        """set_project_by_api_key and get_project_by_api_key work."""
        project_data = {
            "id": "proj-123",
            "name": "Test Project",
            "api_key": "af_test_key",
            "is_active": True,
        }

        result = await cache_service.set_project_by_api_key("af_test_key", project_data)
        assert result is True

        cached = await cache_service.get_project_by_api_key("af_test_key")
        assert cached == project_data

    @pytest.mark.asyncio
    async def test_invalidate_project(self, cache_service):
        """invalidate_project removes cached project."""
        project_data = {"id": "proj-123", "name": "test"}
        await cache_service.set_project_by_api_key("af_invalidate_key", project_data)

        # Verify it's cached
        cached = await cache_service.get_project_by_api_key("af_invalidate_key")
        assert cached is not None

        # Invalidate
        result = await cache_service.invalidate_project("af_invalidate_key")
        assert result is True

        # Verify it's gone
        cached = await cache_service.get_project_by_api_key("af_invalidate_key")
        assert cached is None

    @pytest.mark.asyncio
    async def test_get_nonexistent_policy_returns_none(self, cache_service):
        """get_policy returns None for non-existent key."""
        result = await cache_service.get_policy("nonexistent-project")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_miss_fallback(self, cache_service):
        """Cache miss returns None, allowing DB fallback."""
        # First request - cache miss
        cached = await cache_service.get_policy("fresh-project")
        assert cached is None

        # Simulate DB lookup and cache population
        policy_data = {"id": 1, "rules": "{}"}
        await cache_service.set_policy("fresh-project", policy_data)

        # Second request - cache hit
        cached = await cache_service.get_policy("fresh-project")
        assert cached == policy_data


class TestCacheServiceConcurrency:
    """Test concurrent cache operations."""

    @pytest.mark.asyncio
    async def test_concurrent_reads(self, cache_service):
        """50 concurrent reads succeed."""
        # Pre-populate cache
        policy_data = {"id": 1, "name": "concurrent-test"}
        await cache_service.set_policy("concurrent-read", policy_data)

        async def read_cache(i: int):
            return await cache_service.get_policy("concurrent-read")

        # Run 50 concurrent reads
        tasks = [read_cache(i) for i in range(50)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 50
        assert all(r == policy_data for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_writes(self, cache_service):
        """50 concurrent writes don't cause errors."""

        async def write_cache(i: int):
            return await cache_service.set_policy(
                f"concurrent-write-{i}",
                {"id": i, "name": f"test-{i}"}
            )

        # Run 50 concurrent writes
        tasks = [write_cache(i) for i in range(50)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 50
        assert all(r is True for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_mixed_operations(self, cache_service):
        """Mixed read/write/delete operations work concurrently."""
        # Pre-populate some cache entries
        for i in range(10):
            await cache_service.set_policy(f"mixed-{i}", {"id": i})

        async def mixed_operation(i: int):
            if i % 3 == 0:
                return ("read", await cache_service.get_policy(f"mixed-{i % 10}"))
            elif i % 3 == 1:
                return ("write", await cache_service.set_policy(f"mixed-new-{i}", {"id": i}))
            else:
                return ("delete", await cache_service.invalidate_policy(f"mixed-{i % 10}"))

        # Run 30 mixed operations
        tasks = [mixed_operation(i) for i in range(30)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 30
        # All operations should complete without error


class TestCacheServiceTTL:
    """Test TTL-based cache expiration."""

    @pytest.mark.asyncio
    async def test_policy_cache_expires(self, redis_client):
        """Policy cache expires after TTL."""
        from server.cache import CacheService
        from unittest.mock import MagicMock

        # Create cache with short TTL
        cache = CacheService(redis_client)
        cache.settings = MagicMock()
        cache.settings.cache_enabled = True
        cache.settings.cache_ttl_policy = 1  # 1 second TTL

        policy_data = {"id": 1, "name": "expires"}
        await cache.set_policy("ttl-test", policy_data)

        # Immediately after - should be cached
        cached = await cache.get_policy("ttl-test")
        assert cached == policy_data

        # Wait for expiration
        await asyncio.sleep(1.5)

        # After TTL - should be expired
        cached = await cache.get_policy("ttl-test")
        assert cached is None


class TestInitCache:
    """Test init_cache function."""

    @pytest.mark.asyncio
    async def test_init_cache_with_valid_url(self, redis_url):
        """init_cache creates working cache with valid Redis URL."""
        import server.cache as cache_module
        from server.cache import init_cache, close_cache

        # Temporarily set config
        original_cache = cache_module._cache
        cache_module._cache = None

        with pytest.MonkeyPatch().context() as m:
            m.setenv("REDIS_URL", redis_url)
            m.setenv("CACHE_ENABLED", "true")

            # Need to reload settings
            from server.config import Settings
            settings = Settings()

            with pytest.MonkeyPatch().context() as m2:
                m2.setattr(cache_module, "get_settings", lambda: settings)

                cache = await init_cache()
                try:
                    # Should be available if Redis is running
                    if settings.redis_url:
                        assert cache.is_available is True
                finally:
                    await close_cache()
                    cache_module._cache = original_cache
