"""
Redis cache service for performance optimization.
Caches gas prices, contract metadata, and frequently accessed data.
"""
import json
import asyncio
from typing import Any, Optional, Callable
from datetime import timedelta
import os

# Check if redis is available
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from src.shared.constants import (
    GAS_PRICE_CACHE_TTL,
    CONTRACT_METADATA_CACHE_TTL,
    NETWORK_METADATA_CACHE_TTL
)


class CacheService:
    """
    Redis-based caching service with fallback to in-memory cache.
    """

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL")
        self.redis_client: Optional[redis.Redis] = None
        self._memory_cache: dict = {}
        self._cache_enabled = False

    async def connect(self):
        """Initialize Redis connection"""
        if not REDIS_AVAILABLE:
            print("⚠️  Redis not installed, using in-memory cache (development only)")
            self._cache_enabled = True
            return

        if not self.redis_url:
            print("⚠️  REDIS_URL not configured, using in-memory cache")
            self._cache_enabled = True
            return

        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await self.redis_client.ping()
            self._cache_enabled = True
            print("✓ Redis connected successfully")
        except Exception as e:
            print(f"⚠️  Redis connection failed: {e}, using in-memory cache")
            self.redis_client = None
            self._cache_enabled = True

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self._cache_enabled:
            return None

        try:
            if self.redis_client:
                value = await self.redis_client.get(key)
                if value:
                    return json.loads(value)
            else:
                # In-memory cache
                if key in self._memory_cache:
                    value, expiry = self._memory_cache[key]
                    if expiry is None or expiry > asyncio.get_event_loop().time():
                        return value
                    else:
                        del self._memory_cache[key]
        except Exception as e:
            print(f"Cache get error for {key}: {e}")

        return None

    async def set(self, key: str, value: Any, ttl: int):
        """Set value in cache with TTL"""
        if not self._cache_enabled:
            return

        try:
            serialized = json.dumps(value)

            if self.redis_client:
                await self.redis_client.setex(key, ttl, serialized)
            else:
                # In-memory cache with expiry
                expiry = asyncio.get_event_loop().time() + ttl
                self._memory_cache[key] = (value, expiry)
        except Exception as e:
            print(f"Cache set error for {key}: {e}")

    async def delete(self, key: str):
        """Delete key from cache"""
        if not self._cache_enabled:
            return

        try:
            if self.redis_client:
                await self.redis_client.delete(key)
            else:
                self._memory_cache.pop(key, None)
        except Exception as e:
            print(f"Cache delete error for {key}: {e}")

    async def get_or_fetch(
        self,
        key: str,
        fetch_func: Callable,
        ttl: int,
        *args,
        **kwargs
    ) -> Any:
        """
        Get value from cache or fetch and cache it.

        Args:
            key: Cache key
            fetch_func: Async function to fetch data if not in cache
            ttl: Time to live in seconds
            *args, **kwargs: Arguments to pass to fetch_func
        """
        # Try cache first
        cached = await self.get(key)
        if cached is not None:
            return cached

        # Fetch from source
        value = await fetch_func(*args, **kwargs)

        # Cache the result
        if value is not None:
            await self.set(key, value, ttl)

        return value

    async def clear_pattern(self, pattern: str):
        """Clear all keys matching pattern (Redis only)"""
        if not self.redis_client:
            # For in-memory, clear all if pattern is *
            if pattern == "*":
                self._memory_cache.clear()
            return

        try:
            cursor = 0
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )
                if keys:
                    await self.redis_client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            print(f"Cache clear pattern error: {e}")

    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()


# Global cache instance
cache_service = CacheService()


# Cache key builders
def gas_price_key(network: str) -> str:
    return f"gas:price:{network}"


def contract_metadata_key(address: str) -> str:
    return f"contract:metadata:{address.lower()}"


def network_config_key(ticker: str) -> str:
    return f"network:config:{ticker}"


def user_credits_key(user_id: str) -> str:
    return f"user:credits:{user_id}"


def job_status_key(job_id: str) -> str:
    return f"job:status:{job_id}"
