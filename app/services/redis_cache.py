"""
Redis Cache Service for EPA Emission Factors
Provides caching layer with TTL and automated refresh capabilities
"""

import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from redis import Redis
from redis.exceptions import RedisError, ConnectionError
import asyncio

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisCacheService:
    """Redis caching service for EPA emission factors"""

    def __init__(self):
        self.redis_client = None
        self.is_connected = False
        self._connect()

    def _connect(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )

            # Test connection
            self.redis_client.ping()
            self.is_connected = True
            logger.info("Redis connection established successfully")

        except (RedisError, ConnectionError) as e:
            logger.error(f"Redis connection failed: {str(e)}")
            self.is_connected = False
            self.redis_client = None

    def _get_cache_key(self, key_type: str, identifier: str, **kwargs) -> str:
        """Generate standardized cache keys"""
        base_key = f"epa:{key_type}:{identifier}"

        if kwargs:
            # Sort kwargs for consistent key generation
            sorted_params = sorted(kwargs.items())
            param_str = ":".join([f"{k}={v}" for k, v in sorted_params])
            base_key += f":{param_str}"

        return base_key

    def _serialize_data(self, data: Any) -> str:
        """Serialize data for Redis storage"""
        try:
            if isinstance(data, (dict, list)):
                return json.dumps(data, default=str, ensure_ascii=False)
            return str(data)
        except Exception as e:
            logger.error(f"Data serialization error: {str(e)}")
            raise

    def _deserialize_data(self, data: str) -> Any:
        """Deserialize data from Redis"""
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return data
        except Exception as e:
            logger.error(f"Data deserialization error: {str(e)}")
            return None

    def set_with_ttl(
        self, key: str, value: Any, ttl_seconds: Optional[int] = None
    ) -> bool:
        """Set cache value with TTL"""
        if not self.is_connected:
            logger.warning("Redis not connected, skipping cache set")
            return False

        try:
            ttl = ttl_seconds or settings.REDIS_EXPIRE_SECONDS
            serialized_value = self._serialize_data(value)

            result = self.redis_client.setex(key, ttl, serialized_value)

            logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
            return result

        except RedisError as e:
            logger.error(f"Redis set error: {str(e)}")
            return False

    def get(self, key: str) -> Optional[Any]:
        """Get cache value"""
        if not self.is_connected:
            logger.warning("Redis not connected, skipping cache get")
            return None

        try:
            value = self.redis_client.get(key)
            if value is None:
                return None

            return self._deserialize_data(value)

        except RedisError as e:
            logger.error(f"Redis get error: {str(e)}")
            return None

    def delete(self, key: str) -> bool:
        """Delete cache key"""
        if not self.is_connected:
            return False

        try:
            result = self.redis_client.delete(key)
            logger.debug(f"Cache deleted: {key}")
            return bool(result)

        except RedisError as e:
            logger.error(f"Redis delete error: {str(e)}")
            return False

    def get_ttl(self, key: str) -> int:
        """Get remaining TTL for key"""
        if not self.is_connected:
            return -1

        try:
            return self.redis_client.ttl(key)
        except RedisError as e:
            logger.error(f"Redis TTL error: {str(e)}")
            return -1

    def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self.is_connected:
            return False

        try:
            return bool(self.redis_client.exists(key))
        except RedisError as e:
            logger.error(f"Redis exists error: {str(e)}")
            return False

    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        if not self.is_connected:
            return 0

        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Cleared {deleted} keys matching pattern: {pattern}")
                return deleted
            return 0

        except RedisError as e:
            logger.error(f"Redis clear pattern error: {str(e)}")
            return 0

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.is_connected:
            return {"connected": False}

        try:
            info = self.redis_client.info()

            # Get EPA-specific stats
            epa_keys = self.redis_client.keys("epa:*")

            return {
                "connected": True,
                "total_keys": info.get("db0", {}).get("keys", 0),
                "epa_keys": len(epa_keys),
                "memory_used": info.get("used_memory_human", "0B"),
                "uptime_seconds": info.get("uptime_in_seconds", 0),
                "connected_clients": info.get("connected_clients", 0),
            }

        except RedisError as e:
            logger.error(f"Redis stats error: {str(e)}")
            return {"connected": False, "error": str(e)}


class EPACacheService:
    """EPA-specific caching service with business logic"""

    def __init__(self):
        self.cache = RedisCacheService()
        self.default_ttl = settings.EPA_DATA_CACHE_HOURS * 3600  # Convert to seconds

    def cache_emission_factors(
        self, factors: List[Dict[str, Any]], source: str, version: str
    ) -> bool:
        """Cache EPA emission factors by source and version"""
        try:
            # Cache all factors for source
            all_factors_key = self._get_cache_key("factors", source, version=version)
            success = self.cache.set_with_ttl(
                all_factors_key, factors, self.default_ttl
            )

            if not success:
                return False

            # Cache individual factors by code for fast lookup
            for factor in factors:
                factor_code = factor.get("factor_code")
                if factor_code:
                    factor_key = self._get_cache_key(
                        "factor", factor_code, version=version
                    )
                    self.cache.set_with_ttl(factor_key, factor, self.default_ttl)

            # Cache metadata
            metadata = {
                "source": source,
                "version": version,
                "factor_count": len(factors),
                "cached_at": datetime.utcnow().isoformat(),
                "ttl_seconds": self.default_ttl,
            }

            metadata_key = self._get_cache_key("metadata", source, version=version)
            self.cache.set_with_ttl(metadata_key, metadata, self.default_ttl)

            logger.info(f"Cached {len(factors)} EPA factors for {source} v{version}")
            return True

        except Exception as e:
            logger.error(f"Error caching EPA factors: {str(e)}")
            return False

    def get_emission_factors(
        self,
        source: str,
        version: Optional[str] = None,
        category: Optional[str] = None,
        fuel_type: Optional[str] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached EPA emission factors with optional filtering"""
        try:
            # Try to get from cache first
            cache_key = self._get_cache_key(
                "factors", source, version=version or "current"
            )
            cached_factors = self.cache.get(cache_key)

            if cached_factors is None:
                logger.debug(f"No cached factors found for {source}")
                return None

            # Apply filters if specified
            if category or fuel_type:
                filtered_factors = []
                for factor in cached_factors:
                    if category and factor.get("category") != category:
                        continue
                    if fuel_type and factor.get("fuel_type") != fuel_type:
                        continue
                    filtered_factors.append(factor)
                return filtered_factors

            return cached_factors

        except Exception as e:
            logger.error(f"Error getting cached EPA factors: {str(e)}")
            return None

    def get_emission_factor_by_code(
        self, factor_code: str, version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get specific emission factor by code"""
        try:
            cache_key = self._get_cache_key(
                "factor", factor_code, version=version or "current"
            )
            return self.cache.get(cache_key)

        except Exception as e:
            logger.error(f"Error getting cached EPA factor: {str(e)}")
            return None

    def get_cache_metadata(
        self, source: str, version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get cache metadata for EPA data"""
        try:
            metadata_key = self._get_cache_key(
                "metadata", source, version=version or "current"
            )
            return self.cache.get(metadata_key)

        except Exception as e:
            logger.error(f"Error getting cache metadata: {str(e)}")
            return None

    def invalidate_source_cache(self, source: str) -> bool:
        """Invalidate all cached data for a specific source"""
        try:
            pattern = f"epa:*:{source}:*"
            deleted_count = self.cache.clear_pattern(pattern)
            logger.info(
                f"Invalidated {deleted_count} cache entries for source: {source}"
            )
            return deleted_count > 0

        except Exception as e:
            logger.error(f"Error invalidating cache for {source}: {str(e)}")
            return False

    def is_cache_fresh(self, source: str, version: Optional[str] = None) -> bool:
        """Check if cached data is still fresh"""
        try:
            cache_key = self._get_cache_key(
                "factors", source, version=version or "current"
            )
            ttl = self.cache.get_ttl(cache_key)

            # TTL > 0 means key exists and has time left
            # TTL = -1 means key exists but no expiration
            # TTL = -2 means key doesn't exist
            return ttl > 0 or ttl == -1

        except Exception as e:
            logger.error(f"Error checking cache freshness: {str(e)}")
            return False

    def get_cache_status(self) -> Dict[str, Any]:
        """Get comprehensive cache status"""
        try:
            base_stats = self.cache.get_cache_stats()

            # Get EPA-specific cache info
            sources = ["EPA_GHGRP", "EPA_EGRID", "EPA_AP42"]
            source_status = {}

            for source in sources:
                metadata = self.get_cache_metadata(source)
                if metadata:
                    cache_key = self._get_cache_key(
                        "factors", source, version="current"
                    )
                    ttl = self.cache.get_ttl(cache_key)

                    source_status[source] = {
                        "cached": True,
                        "factor_count": metadata.get("factor_count", 0),
                        "cached_at": metadata.get("cached_at"),
                        "ttl_remaining": ttl,
                        "is_fresh": ttl > 0 or ttl == -1,
                    }
                else:
                    source_status[source] = {
                        "cached": False,
                        "factor_count": 0,
                        "cached_at": None,
                        "ttl_remaining": -2,
                        "is_fresh": False,
                    }

            return {
                **base_stats,
                "sources": source_status,
                "default_ttl_hours": self.default_ttl / 3600,
            }

        except Exception as e:
            logger.error(f"Error getting cache status: {str(e)}")
            return {"error": str(e)}

    def _get_cache_key(self, key_type: str, identifier: str, **kwargs) -> str:
        """Generate EPA-specific cache keys"""
        return self.cache._get_cache_key(key_type, identifier, **kwargs)


# Global cache service instance
epa_cache = EPACacheService()
