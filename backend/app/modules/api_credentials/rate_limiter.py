"""
SenderX Distributed Redis Sliding-Window Rate Limiter
Provides multi-dimensional rate limiting across credentials, applications,
organizations, authentication failures, and ingestion requests.
Fails closed in production when Redis is unreachable.
"""

from datetime import datetime, timezone
import os
import time
from typing import Optional, Tuple
import uuid

from flask import current_app, has_app_context, request
import redis


class RateLimiterError(Exception):
    """Raised when the rate limiter encounters an unrecoverable infrastructure failure."""
    pass


class DistributedRateLimiter:
    """Sliding-window rate limiter using Redis sorted sets (ZSET)."""

    DEFAULT_LIMITS = {
        "credential": 120,       # 120 requests per minute per API key
        "application": 300,      # 300 requests per minute per application
        "organization": 1000,    # 1000 requests per minute per organization
        "auth_failure": 10,      # 10 failed auth attempts per minute per IP
        "ingest": 600,           # 600 ingestion requests per minute per org/IP
    }

    @classmethod
    def _get_redis(cls) -> Optional[redis.Redis]:
        """Obtain active Redis client from Flask application context."""
        if has_app_context() and hasattr(current_app, "redis_client"):
            return current_app.redis_client
        return None

    @classmethod
    def _is_production(cls) -> bool:
        if has_app_context():
            env = current_app.config.get("APP_ENV", os.getenv("APP_ENV", "development"))
        else:
            env = os.getenv("APP_ENV", "development")
        return env.lower() == "production"

    @classmethod
    def check_rate_limit(
        cls,
        dimension: str,
        identifier: str,
        limit: Optional[int] = None,
        window_seconds: int = 60,
        fail_closed: bool = False
    ) -> Tuple[bool, int]:
        """
        Check and record an access attempt in a sliding window.
        Returns:
            is_allowed (bool): True if under limit, False if exceeded.
            retry_after (int): Seconds client must wait before retrying.
        """
        if not identifier:
            return True, 0

        max_allowed = limit if limit is not None else cls.DEFAULT_LIMITS.get(dimension, 120)
        key = f"ratelimit:{dimension}:{identifier}"
        now = time.time()

        try:
            client = cls._get_redis()
            if client is None:
                if fail_closed or cls._is_production():
                    raise RateLimiterError("Distributed rate limiter unavailable")
                return True, 0

            pipe = client.pipeline()
            # 1. Remove entries older than window
            pipe.zremrangebyscore(key, 0, now - window_seconds)
            # 2. Add current request with unique score member
            member_id = f"{now}-{uuid.uuid4().hex[:8]}"
            pipe.zadd(key, {member_id: now})
            # 3. Get total entries in current window
            pipe.zcard(key)
            # 4. Refresh TTL
            pipe.expire(key, window_seconds + 5)
            # 5. Fetch oldest item to calculate Retry-After precisely
            pipe.zrange(key, 0, 0, withscores=True)

            results = pipe.execute()
            count = results[2]
            oldest_entries = results[4]

            if count > max_allowed:
                if oldest_entries and len(oldest_entries) > 0:
                    oldest_ts = oldest_entries[0][1]
                    retry_after = max(1, int(oldest_ts + window_seconds - now))
                else:
                    retry_after = window_seconds
                return False, retry_after

            return True, 0

        except (redis.RedisError, ConnectionError, OSError) as exc:
            if fail_closed or cls._is_production():
                raise RateLimiterError(f"Distributed rate limiter unavailable: {exc}") from exc
            if has_app_context():
                current_app.logger.warning(f"Rate limiting skipped due to Redis error: {exc}")
            return True, 0

    @classmethod
    def record_auth_failure(cls, client_ip: str, window_seconds: int = 60) -> Tuple[bool, int]:
        """Record and verify failed authentication attempts from a given IP."""
        return cls.check_rate_limit(
            dimension="auth_failure",
            identifier=client_ip,
            limit=cls.DEFAULT_LIMITS["auth_failure"],
            window_seconds=window_seconds
        )

    @classmethod
    def reset_key(cls, dimension: str, identifier: str) -> None:
        """Utility for test suites to reset a rate limit key."""
        client = cls._get_redis()
        if client:
            try:
                client.delete(f"ratelimit:{dimension}:{identifier}")
            except Exception:
                pass
