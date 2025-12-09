"""Redis caching service with graceful degradation."""

import json
import logging
from typing import Optional

from server.config import get_settings

logger = logging.getLogger(__name__)

# Conditional import - Redis is optional
try:
    from redis import asyncio as aioredis
    from redis.exceptions import RedisError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    aioredis = None
    RedisError = Exception  # Fallback for type hints


class CacheService:
    """Async Redis cache with graceful degradation.

    If Redis is unavailable or disabled, all operations become no-ops
    that return appropriate default values.
    """

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.settings = get_settings()
        self._available = redis_client is not None

    @property
    def is_available(self) -> bool:
        """Check if cache is available and enabled."""
        return self._available and self.settings.cache_enabled

    async def get(self, key: str) -> Optional[str]:
        """Get value from cache. Returns None on miss or error."""
        if not self.is_available:
            return None
        try:
            return await self.redis.get(key)
        except RedisError as e:
            logger.warning(f"Redis GET error for {key}: {e}")
            return None

    async def set(self, key: str, value: str, ttl: int) -> bool:
        """Set value in cache with TTL. Returns success status."""
        if not self.is_available:
            return False
        try:
            await self.redis.setex(key, ttl, value)
            return True
        except RedisError as e:
            logger.warning(f"Redis SET error for {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.is_available:
            return False
        try:
            await self.redis.delete(key)
            return True
        except RedisError as e:
            logger.warning(f"Redis DELETE error for {key}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern. Returns count deleted."""
        if not self.is_available:
            return 0
        try:
            keys = await self.redis.keys(pattern)
            if keys:
                return await self.redis.delete(*keys)
            return 0
        except RedisError as e:
            logger.warning(f"Redis DELETE pattern error for {pattern}: {e}")
            return 0

    # === Policy Cache Methods ===

    async def get_policy(self, project_id: str) -> Optional[dict]:
        """Get cached policy for project."""
        data = await self.get(f"policy:{project_id}")
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in cache for policy:{project_id}")
                return None
        return None

    async def set_policy(self, project_id: str, policy_data: dict) -> bool:
        """Cache policy for project."""
        return await self.set(
            f"policy:{project_id}",
            json.dumps(policy_data),
            self.settings.cache_ttl_policy
        )

    async def invalidate_policy(self, project_id: str) -> bool:
        """Invalidate policy cache for project."""
        return await self.delete(f"policy:{project_id}")

    # === Project/API Key Cache Methods ===

    async def get_project_by_api_key(self, api_key: str) -> Optional[dict]:
        """Get cached project by API key."""
        data = await self.get(f"api_key:{api_key}")
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in cache for api_key:{api_key[:8]}...")
                return None
        return None

    async def set_project_by_api_key(self, api_key: str, project_data: dict) -> bool:
        """Cache project by API key."""
        return await self.set(
            f"api_key:{api_key}",
            json.dumps(project_data),
            self.settings.cache_ttl_project
        )

    async def invalidate_project(self, api_key: str) -> bool:
        """Invalidate project cache."""
        return await self.delete(f"api_key:{api_key}")

    # === Aggregate Limit Cache Methods ===

    async def get_aggregate(self, key: str) -> Optional[float]:
        """Get cached aggregate total."""
        data = await self.get(key)
        if data:
            try:
                return float(data)
            except ValueError:
                logger.warning(f"Invalid float in aggregate cache: {key}")
                return None
        return None

    async def set_aggregate(self, key: str, value: float, ttl: int) -> bool:
        """Cache aggregate total."""
        return await self.set(key, str(value), ttl)

    async def invalidate_aggregates(self, project_id: str) -> int:
        """Invalidate all aggregate caches for a project."""
        return await self.delete_pattern(f"agg:{project_id}:*")


# Global cache instance
_cache: Optional[CacheService] = None


async def init_cache() -> CacheService:
    """Initialize cache service. Called at app startup."""
    global _cache
    settings = get_settings()

    if not REDIS_AVAILABLE:
        logger.info("Redis package not installed, caching disabled")
        _cache = CacheService(None)
        return _cache

    if settings.redis_url and settings.cache_enabled:
        try:
            redis_client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=settings.redis_pool_size,
                socket_timeout=settings.redis_timeout,
                socket_connect_timeout=settings.redis_timeout,
            )
            # Test connection
            await redis_client.ping()
            _cache = CacheService(redis_client)
            logger.info(f"Redis cache initialized: {settings.redis_url}")
        except Exception as e:
            logger.warning(f"Redis unavailable, caching disabled: {e}")
            _cache = CacheService(None)
    else:
        if not settings.cache_enabled:
            logger.info("Redis caching disabled by configuration (CACHE_ENABLED=false)")
        else:
            logger.info("Redis caching disabled (no REDIS_URL configured)")
        _cache = CacheService(None)

    return _cache


async def close_cache() -> None:
    """Close cache connections. Called at app shutdown."""
    global _cache
    if _cache and _cache.redis:
        await _cache.redis.aclose()
        logger.info("Redis connection closed")
    _cache = None


def get_cache() -> CacheService:
    """Get cache service instance."""
    global _cache
    if _cache is None:
        # Return no-op cache if not initialized
        return CacheService(None)
    return _cache
