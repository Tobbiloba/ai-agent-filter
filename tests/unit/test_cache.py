"""Unit tests for cache service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestCacheServiceWithoutRedis:
    """Tests for CacheService when Redis is not available."""

    def test_cache_disabled_when_no_redis_client(self):
        """CacheService works as no-op without Redis client."""
        from server.cache import CacheService

        cache = CacheService(None)
        assert cache.is_available is False

    @pytest.mark.asyncio
    async def test_get_returns_none_when_disabled(self):
        """Get returns None when cache is disabled."""
        from server.cache import CacheService

        cache = CacheService(None)
        result = await cache.get("any_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_returns_false_when_disabled(self):
        """Set returns False when cache is disabled."""
        from server.cache import CacheService

        cache = CacheService(None)
        result = await cache.set("key", "value", 300)
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_disabled(self):
        """Delete returns False when cache is disabled."""
        from server.cache import CacheService

        cache = CacheService(None)
        result = await cache.delete("key")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_policy_returns_none_when_disabled(self):
        """get_policy returns None when cache is disabled."""
        from server.cache import CacheService

        cache = CacheService(None)
        result = await cache.get_policy("project-123")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_policy_returns_false_when_disabled(self):
        """set_policy returns False when cache is disabled."""
        from server.cache import CacheService

        cache = CacheService(None)
        result = await cache.set_policy("project-123", {"rules": []})
        assert result is False

    @pytest.mark.asyncio
    async def test_get_project_by_api_key_returns_none_when_disabled(self):
        """get_project_by_api_key returns None when cache is disabled."""
        from server.cache import CacheService

        cache = CacheService(None)
        result = await cache.get_project_by_api_key("api_key_123")
        assert result is None


class TestCacheServiceWithMockedRedis:
    """Tests for CacheService with mocked Redis client."""

    @pytest.mark.asyncio
    async def test_get_returns_cached_value(self):
        """Get returns value from Redis."""
        from server.cache import CacheService

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="cached_value")

        cache = CacheService(mock_redis)
        result = await cache.get("test_key")

        assert result == "cached_value"
        mock_redis.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_set_calls_redis_setex(self):
        """Set calls Redis setex with TTL."""
        from server.cache import CacheService

        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()

        cache = CacheService(mock_redis)
        result = await cache.set("key", "value", 300)

        assert result is True
        mock_redis.setex.assert_called_once_with("key", 300, "value")

    @pytest.mark.asyncio
    async def test_delete_calls_redis_delete(self):
        """Delete calls Redis delete."""
        from server.cache import CacheService

        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()

        cache = CacheService(mock_redis)
        result = await cache.delete("key")

        assert result is True
        mock_redis.delete.assert_called_once_with("key")

    @pytest.mark.asyncio
    async def test_get_policy_returns_parsed_json(self):
        """get_policy returns parsed JSON from cache."""
        from server.cache import CacheService
        import json

        policy_data = {"id": 1, "rules": '{"default": "allow"}'}
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(policy_data))

        cache = CacheService(mock_redis)
        result = await cache.get_policy("project-123")

        assert result == policy_data
        mock_redis.get.assert_called_once_with("policy:project-123")

    @pytest.mark.asyncio
    async def test_set_policy_stores_json(self):
        """set_policy stores JSON-serialized policy."""
        from server.cache import CacheService
        import json

        policy_data = {"id": 1, "rules": '{"default": "allow"}'}
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()

        cache = CacheService(mock_redis)
        with patch.object(cache, 'settings') as mock_settings:
            mock_settings.cache_ttl_policy = 300
            mock_settings.cache_enabled = True
            result = await cache.set_policy("project-123", policy_data)

        assert result is True
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "policy:project-123"
        assert call_args[0][1] == 300
        assert json.loads(call_args[0][2]) == policy_data

    @pytest.mark.asyncio
    async def test_invalidate_policy_deletes_key(self):
        """invalidate_policy deletes the policy cache key."""
        from server.cache import CacheService

        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()

        cache = CacheService(mock_redis)
        result = await cache.invalidate_policy("project-123")

        assert result is True
        mock_redis.delete.assert_called_once_with("policy:project-123")

    @pytest.mark.asyncio
    async def test_get_project_by_api_key_returns_parsed_json(self):
        """get_project_by_api_key returns parsed JSON."""
        from server.cache import CacheService
        import json

        project_data = {"id": "proj-1", "name": "Test Project"}
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(project_data))

        cache = CacheService(mock_redis)
        result = await cache.get_project_by_api_key("api_key_123")

        assert result == project_data
        mock_redis.get.assert_called_once_with("api_key:api_key_123")


class TestCacheServiceErrorHandling:
    """Tests for graceful error handling."""

    @pytest.mark.asyncio
    async def test_get_returns_none_on_redis_error(self):
        """Get returns None on Redis error instead of raising."""
        from server.cache import CacheService
        from redis.exceptions import RedisError

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=RedisError("Connection failed"))

        cache = CacheService(mock_redis)
        result = await cache.get("key")

        assert result is None

    @pytest.mark.asyncio
    async def test_set_returns_false_on_redis_error(self):
        """Set returns False on Redis error instead of raising."""
        from server.cache import CacheService
        from redis.exceptions import RedisError

        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(side_effect=RedisError("Connection failed"))

        cache = CacheService(mock_redis)
        result = await cache.set("key", "value", 300)

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_returns_false_on_redis_error(self):
        """Delete returns False on Redis error instead of raising."""
        from server.cache import CacheService
        from redis.exceptions import RedisError

        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(side_effect=RedisError("Connection failed"))

        cache = CacheService(mock_redis)
        result = await cache.delete("key")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_policy_returns_none_on_invalid_json(self):
        """get_policy returns None for invalid JSON instead of raising."""
        from server.cache import CacheService

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="not valid json{{{")

        cache = CacheService(mock_redis)
        result = await cache.get_policy("project-123")

        assert result is None


class TestGetCacheFunction:
    """Tests for the get_cache() function."""

    def test_get_cache_returns_service_instance(self):
        """get_cache returns a CacheService instance."""
        from server.cache import get_cache, CacheService

        cache = get_cache()
        assert isinstance(cache, CacheService)

    def test_get_cache_returns_noop_when_not_initialized(self):
        """get_cache returns no-op cache when not initialized."""
        from server.cache import get_cache, _cache
        import server.cache as cache_module

        # Reset global state
        original_cache = cache_module._cache
        cache_module._cache = None

        try:
            cache = get_cache()
            assert cache.is_available is False
        finally:
            cache_module._cache = original_cache


class TestHealthEndpointCacheStatus:
    """Tests for cache status in health endpoint."""

    def test_health_shows_cache_disabled_without_redis(self):
        """Health endpoint shows cache: disabled when Redis is not available."""
        from fastapi.testclient import TestClient
        from server.app import app

        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert "cache" in data
            # Without Redis URL configured, cache should be disabled
            assert data["cache"] == "disabled"
