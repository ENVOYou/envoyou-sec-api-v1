"""
Redis Cache Service for EPA Data
High-performance caching with TTL and fallback mechanisms
"""

import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import redis
import pickle
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Redis-based caching service for EPA data and application cache"""

    def __init__(self):
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=False,  # We'll handle encoding ourselves
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )

            # Test connection
            self.redis_client.ping()
            logger.info("Redis connection established successfully")

        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            self.redis_client = None

    def _get_key(self, prefix: str, identifier: str) -> str:
        """Generate cache key with prefix"""
        return f"envoyou:sec:{prefix}:{identifier}"

    def _serialize_data(self, data: Any) -> bytes:
        """Serialize data for Redis storage"""
        try:
            if isinstance(data, (dict, list)):
                return json.dumps(data, default=str).encode("utf-8")
            else:
                return pickle.dumps(data)
        except Exception as e:
            logger.error(f"Serialization error: {str(e)}")
            raise

    def _deserialize_data(self, data: bytes) -> Any:
        """Deserialize data from Redis"""
        try:
            # Try JSON first (more common)
            try:
                return json.loads(data.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Fall back to pickle
                return pickle.loads(data)
        except Exception as e:
            logger.error(f"Deserialization error: {str(e)}")
            return None

    def set_epa_factors(
        self, category: str, factors: List[Dict[str, Any]], ttl_hours: int = None
    ) -> bool:
        """Cache EPA emission factors by category"""
        if not self.redis_client:
            logger.warning("Redis not available, skipping cache")
            return False

        try:
            key = self._get_key("epa_factors", category)
            serialized_data = self._serialize_data(
                {
                    "factors": factors,
                    "cached_at": datetime.utcnow().isoformat(),
                    "category": category,
                }
            )

            ttl_seconds = (ttl_hours or settings.EPA_DATA_CACHE_HOURS) * 3600

            result = self.redis_client.setex(key, ttl_seconds, serialized_data)

            if result:
                logger.info(
                    f"Cached {len(factors)} EPA factors for category '{category}' with TTL {ttl_seconds}s"
                )

            return result

        except Exception as e:
            logger.error(f"Error caching EPA factors: {str(e)}")
            return False

    def get_epa_factors(self, category: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached EPA emission factors by category"""
        if not self.redis_client:
            logger.warning("Redis not available, cache miss")
            return None

        try:
            key = self._get_key("epa_factors", category)
            cached_data = self.redis_client.get(key)

            if cached_data:
                data = self._deserialize_data(cached_data)
                if data:
                    logger.info(f"Cache hit for EPA factors category '{category}'")
                    return data

            logger.info(f"Cache miss for EPA factors category '{category}'")
            return None

        except Exception as e:
            logger.error(f"Error retrieving cached EPA factors: {str(e)}")
            return None

    def set_factor_by_code(
        self, factor_code: str, factor_data: Dict[str, Any], ttl_hours: int = None
    ) -> bool:
        """Cache individual emission factor by code"""
        if not self.redis_client:
            return False

        try:
            key = self._get_key("factor", factor_code)
            serialized_data = self._serialize_data(
                {"factor": factor_data, "cached_at": datetime.utcnow().isoformat()}
            )

            ttl_seconds = (ttl_hours or settings.EPA_DATA_CACHE_HOURS) * 3600
            result = self.redis_client.setex(key, ttl_seconds, serialized_data)

            if result:
                logger.debug(f"Cached emission factor '{factor_code}'")

            return result

        except Exception as e:
            logger.error(f"Error caching emission factor: {str(e)}")
            return False

    def get_factor_by_code(self, factor_code: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached emission factor by code"""
        if not self.redis_client:
            return None

        try:
            key = self._get_key("factor", factor_code)
            cached_data = self.redis_client.get(key)

            if cached_data:
                data = self._deserialize_data(cached_data)
                if data:
                    logger.debug(f"Cache hit for emission factor '{factor_code}'")
                    return data

            return None

        except Exception as e:
            logger.error(f"Error retrieving cached emission factor: {str(e)}")
            return None

    def set_calculation_result(
        self, calculation_id: str, result: Dict[str, Any], ttl_hours: int = 24
    ) -> bool:
        """Cache calculation results"""
        if not self.redis_client:
            return False

        try:
            key = self._get_key("calculation", calculation_id)
            serialized_data = self._serialize_data(
                {"result": result, "cached_at": datetime.utcnow().isoformat()}
            )

            ttl_seconds = ttl_hours * 3600
            result = self.redis_client.setex(key, ttl_seconds, serialized_data)

            if result:
                logger.debug(f"Cached calculation result '{calculation_id}'")

            return result

        except Exception as e:
            logger.error(f"Error caching calculation result: {str(e)}")
            return False

    def get_calculation_result(self, calculation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached calculation result"""
        if not self.redis_client:
            return None

        try:
            key = self._get_key("calculation", calculation_id)
            cached_data = self.redis_client.get(key)

            if cached_data:
                data = self._deserialize_data(cached_data)
                if data:
                    logger.debug(f"Cache hit for calculation '{calculation_id}'")
                    return data

            return None

        except Exception as e:
            logger.error(f"Error retrieving cached calculation: {str(e)}")
            return None

    def invalidate_epa_cache(self, pattern: str = "epa_*") -> int:
        """Invalidate EPA cache entries matching pattern"""
        if not self.redis_client:
            return 0

        try:
            pattern_key = self._get_key("", pattern)
            keys = self.redis_client.keys(pattern_key)

            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Invalidated {deleted} cache entries matching '{pattern}'")
                return deleted

            return 0

        except Exception as e:
            logger.error(f"Error invalidating cache: {str(e)}")
            return 0

    def set_cache_staleness_indicator(self, key: str, is_stale: bool = True) -> bool:
        """Set staleness indicator for cached data"""
        if not self.redis_client:
            return False

        try:
            staleness_key = self._get_key("staleness", key)
            staleness_data = {
                "is_stale": is_stale,
                "marked_at": datetime.utcnow().isoformat(),
            }

            # Set with longer TTL than the actual data
            ttl_seconds = settings.EPA_DATA_CACHE_HOURS * 3600 * 2
            result = self.redis_client.setex(
                staleness_key, ttl_seconds, self._serialize_data(staleness_data)
            )

            if result:
                logger.info(f"Set staleness indicator for '{key}': {is_stale}")

            return result

        except Exception as e:
            logger.error(f"Error setting staleness indicator: {str(e)}")
            return False

    def is_data_stale(self, key: str) -> bool:
        """Check if cached data is marked as stale"""
        if not self.redis_client:
            return True  # Assume stale if no cache

        try:
            staleness_key = self._get_key("staleness", key)
            cached_data = self.redis_client.get(staleness_key)

            if cached_data:
                data = self._deserialize_data(cached_data)
                if data:
                    return data.get("is_stale", False)

            return False  # Not marked as stale

        except Exception as e:
            logger.error(f"Error checking staleness: {str(e)}")
            return True  # Assume stale on error

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.redis_client:
            return {"status": "unavailable"}

        try:
            info = self.redis_client.info()

            # Count our keys
            our_keys = self.redis_client.keys("envoyou:sec:*")

            return {
                "status": "available",
                "redis_version": info.get("redis_version"),
                "used_memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "total_commands_processed": info.get("total_commands_processed"),
                "envoyou_keys": len(our_keys),
                "uptime_seconds": info.get("uptime_in_seconds"),
            }

        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {"status": "error", "error": str(e)}

    def health_check(self) -> bool:
        """Check if Redis is healthy"""
        if not self.redis_client:
            return False

        try:
            response = self.redis_client.ping()
            return response is True
        except Exception as e:
            logger.error(f"Redis health check failed: {str(e)}")
            return False


# Global cache service instance - lazy initialization for testing
import os

if os.getenv("TESTING") != "true":
    cache_service = CacheService()
else:
    # Mock cache service for testing
    from unittest.mock import MagicMock

    cache_service = MagicMock()
    cache_service.health_check.return_value = True
    cache_service.get_cache_stats.return_value = {"status": "healthy"}
    cache_service.set_cache_staleness_indicator.return_value = True
    cache_service.is_data_stale.return_value = False
    cache_service.set_epa_factors.return_value = True
    cache_service.set_factor_by_code.return_value = True
    cache_service.get_epa_factors.return_value = None
    cache_service.get_factor_by_code.return_value = None
    cache_service.invalidate_epa_cache.return_value = 0
