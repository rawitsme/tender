"""Redis caching service — synchronous wrapper for use in async FastAPI."""

import json
import logging
from typing import Optional, Any

import redis

from backend.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_client: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


async def cache_get(key: str) -> Optional[Any]:
    """Get a cached value."""
    try:
        val = _get_redis().get(f"tw:{key}")
        if val:
            return json.loads(val)
    except Exception as e:
        logger.debug(f"Cache get error for {key}: {e}")
    return None


async def cache_set(key: str, value: Any, ttl: int = 300):
    """Set a cached value with TTL in seconds."""
    try:
        _get_redis().setex(f"tw:{key}", ttl, json.dumps(value, default=str))
    except Exception as e:
        logger.debug(f"Cache set error for {key}: {e}")


async def cache_delete(key: str):
    """Delete a cached key."""
    try:
        _get_redis().delete(f"tw:{key}")
    except Exception as e:
        logger.debug(f"Cache delete error for {key}: {e}")


async def cache_delete_pattern(pattern: str):
    """Delete all keys matching a pattern."""
    try:
        r = _get_redis()
        keys = list(r.scan_iter(f"tw:{pattern}"))
        if keys:
            r.delete(*keys)
    except Exception as e:
        logger.debug(f"Cache pattern delete error for {pattern}: {e}")
