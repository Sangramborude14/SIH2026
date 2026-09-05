import time
import json
from typing import Optional, Any, Dict, Tuple
from datetime import datetime, timezone
import httpx
from backend.app.core.config import settings
from backend.app.core.logging import logger


class InMemoryTTLCache:
    """
    In-memory asynchronous TTL cache with automatic expiration and size pruning.
    Functions as local cache and resilient fallback when Redis is unreachable.
    """

    def __init__(self, default_ttl: int = settings.WEATHER_CACHE_TTL_SECONDS):
        self._default_ttl = default_ttl
        self._store: Dict[str, Dict[str, Any]] = {}

    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        return time.time() > entry["expires_at"]

    async def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if self._is_expired(entry):
            self._store.pop(key, None)
            return None
        return entry["value"]

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        self._store[key] = {
            "value": value,
            "expires_at": time.time() + ttl,
            "cached_at": datetime.now(timezone.utc).isoformat()
        }
        if len(self._store) > 1000:
            self._prune()

    def _prune(self):
        now = time.time()
        expired = [k for k, v in self._store.items() if now > v["expires_at"]]
        for k in expired:
            self._store.pop(k, None)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        entry = self._store.get(key)
        if entry is None:
            return False
        if self._is_expired(entry):
            self._store.pop(key, None)
            return False
        return True

    async def clear(self) -> None:
        self._store.clear()

    async def increment(self, key: str, amount: int = 1, ttl_seconds: Optional[int] = 60) -> int:
        now = time.time()
        entry = self._store.get(key)
        if entry is None or self._is_expired(entry):
            new_val = amount
            ttl = ttl_seconds or 60
            self._store[key] = {
                "value": new_val,
                "expires_at": now + ttl,
                "cached_at": datetime.now(timezone.utc).isoformat()
            }
            return new_val
        else:
            current = int(entry.get("value", 0)) + amount
            entry["value"] = current
            return current


class UpstashRedisClient:
    """
    Lightweight REST-based client for Upstash Redis.
    Uses asynchronous HTTP connection pooling via httpx.
    """

    def __init__(self, rest_url: str, rest_token: str, timeout: float = settings.REDIS_TIMEOUT_SECONDS):
        self.url = rest_url.rstrip("/")
        self.token = rest_token
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.timeout = timeout

    async def ping(self) -> bool:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.url, headers=self.headers, json=["PING"])
            if resp.status_code == 200:
                data = resp.json()
                return data.get("result") == "PONG"
            return False

    async def get(self, key: str) -> Optional[str]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.url, headers=self.headers, json=["GET", key])
            if resp.status_code == 200:
                data = resp.json()
                return data.get("result")
            return None

    async def set(self, key: str, value: Any, ex_seconds: Optional[int] = None, ttl_seconds: Optional[int] = None) -> bool:
        ttl = ttl_seconds if ttl_seconds is not None else ex_seconds
        val_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        cmd = ["SET", key, val_str]
        if ttl is not None:
            cmd.extend(["EX", str(ttl)])
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.url, headers=self.headers, json=cmd)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("result") in ["OK", True, 1]
            return False


    async def delete(self, key: str) -> bool:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.url, headers=self.headers, json=["DEL", key])
            if resp.status_code == 200:
                data = resp.json()
                return bool(data.get("result", 0))
            return False

    async def exists(self, key: str) -> bool:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.url, headers=self.headers, json=["EXISTS", key])
            if resp.status_code == 200:
                data = resp.json()
                return bool(data.get("result", 0))
            return False

    async def increment(self, key: str, amount: int = 1, ttl_seconds: Optional[int] = None) -> int:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.url, headers=self.headers, json=["INCRBY", key, str(amount)])
            if resp.status_code == 200:
                data = resp.json()
                new_val = int(data.get("result", 1))
                if ttl_seconds and new_val == amount:
                    await client.post(self.url, headers=self.headers, json=["EXPIRE", key, str(ttl_seconds)])
                return new_val
            return 1



class RedisService:
    """
    Unified Redis / Upstash Caching Service with resilient in-memory fallback.
    Ensures Redis is an infrastructure accelerator and never a single point of failure.
    """

    def __init__(self):
        self._memory_cache = InMemoryTTLCache()
        self._upstash_client: Optional[UpstashRedisClient] = None
        self._async_redis = None
        self._init_client()

    def _init_client(self):
        if settings.UPSTASH_REDIS_REST_URL and settings.UPSTASH_REDIS_REST_TOKEN and settings.REDIS_CACHE_ENABLED:
            self._upstash_client = UpstashRedisClient(
                rest_url=settings.UPSTASH_REDIS_REST_URL,
                rest_token=settings.UPSTASH_REDIS_REST_TOKEN,
                timeout=settings.REDIS_TIMEOUT_SECONDS
            )
            logger.info("RedisService configured with Upstash Redis REST backend.")
        elif settings.REDIS_URL and settings.REDIS_CACHE_ENABLED:
            try:
                import redis.asyncio as aioredis
                self._async_redis = aioredis.from_url(
                    settings.REDIS_URL,
                    socket_connect_timeout=settings.REDIS_TIMEOUT_SECONDS,
                    decode_responses=True
                )
                logger.info(f"RedisService configured with async Redis backend ({settings.REDIS_URL}).")
            except Exception as err:
                logger.warning(f"Async Redis initialization deferred ({err}); operating with local in-memory TTL cache.")
        else:
            self._upstash_client = None
            logger.info("RedisService initialized with local in-memory TTL cache.")

    @property
    def is_upstash_configured(self) -> bool:
        return self._upstash_client is not None

    async def get(self, key: str) -> Optional[Any]:
        """
        Retrieves a cached item by key.
        Checks Upstash or native Redis if configured; falls back to in-memory cache gracefully on failure.
        """
        start_t = time.perf_counter()
        if self._upstash_client:
            try:
                raw_val = await self._upstash_client.get(key)
                if raw_val is not None:
                    latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
                    provider_health_registry.record_success("cache-subsystem", latency_ms)
                    try:
                        return json.loads(raw_val)
                    except (json.JSONDecodeError, TypeError):
                        return raw_val
            except Exception as err:
                logger.warning(f"Upstash Redis read failed for key '{key}' ({err}). Falling back to in-memory tier.")
                provider_health_registry.record_failure("cache-subsystem", f"Read error: {err}")
        elif self._async_redis:
            try:
                raw_val = await self._async_redis.get(key)
                if raw_val is not None:
                    latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
                    provider_health_registry.record_success("cache-subsystem", latency_ms)
                    try:
                        return json.loads(raw_val)
                    except (json.JSONDecodeError, TypeError):
                        return raw_val
            except Exception as err:
                logger.debug(f"Redis read failed for key '{key}' ({err}). Falling back to in-memory tier.")

        # Local memory fallback
        return await self._memory_cache.get(key)

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """
        Caches a serializable item with an explicit or default TTL.
        Writes to Redis/Upstash and in-memory cache concurrently.
        """
        ttl = ttl_seconds or settings.WEATHER_CACHE_TTL_SECONDS
        start_t = time.perf_counter()
        
        # Serialize to JSON string if dict/list/object
        if isinstance(value, (dict, list, bool, int, float)):
            serialized = json.dumps(value)
        else:
            serialized = str(value)

        # Always update local memory tier
        await self._memory_cache.set(key, value, ttl_seconds=ttl)

        if self._upstash_client:
            try:
                success = await self._upstash_client.set(key, serialized, ex_seconds=ttl)
                latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
                if success:
                    provider_health_registry.record_success("cache-subsystem", latency_ms)
                return True
            except Exception as err:
                logger.warning(f"Upstash Redis write failed for key '{key}' ({err}). Local in-memory cache preserved.")
                provider_health_registry.record_failure("cache-subsystem", f"Write error: {err}")
                return True
        elif self._async_redis:
            try:
                await self._async_redis.set(key, serialized, ex=ttl)
                latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
                provider_health_registry.record_success("cache-subsystem", latency_ms)
                return True
            except Exception as err:
                logger.debug(f"Redis write failed for key '{key}' ({err}). Local in-memory cache preserved.")
                return True

        return True

    async def set_with_ttl(self, key: str, value: Any, ttl_seconds: int) -> bool:
        """Convenience wrapper for caching with an explicit TTL."""
        return await self.set(key, value, ttl_seconds=ttl_seconds)

    async def delete(self, key: str) -> bool:
        """Removes a key from all cache tiers."""
        await self._memory_cache.delete(key)
        if self._upstash_client:
            try:
                return await self._upstash_client.delete(key)
            except Exception as err:
                logger.warning(f"Upstash Redis delete failed for key '{key}' ({err}).")
        elif self._async_redis:
            try:
                await self._async_redis.delete(key)
                return True
            except Exception as err:
                logger.debug(f"Redis delete failed for key '{key}' ({err}).")
        return True

    async def exists(self, key: str) -> bool:
        """Checks whether a key exists in cache."""
        if await self._memory_cache.exists(key):
            return True
        if self._upstash_client:
            try:
                return await self._upstash_client.exists(key)
            except Exception as err:
                logger.warning(f"Upstash Redis exists check failed for key '{key}' ({err}).")
        elif self._async_redis:
            try:
                return bool(await self._async_redis.exists(key))
            except Exception as err:
                logger.debug(f"Redis exists check failed for key '{key}' ({err}).")
        return False

    async def increment(self, key: str, amount: int = 1, ttl_seconds: Optional[int] = 60) -> int:
        """Atomic rate-limiting / request counter."""
        if self._upstash_client:
            try:
                return await self._upstash_client.increment(key, amount=amount, ttl_seconds=ttl_seconds)
            except Exception as err:
                logger.warning(f"Upstash Redis increment failed for key '{key}' ({err}). Using in-memory counter.")
        return await self._memory_cache.increment(key, amount=amount, ttl_seconds=ttl_seconds)

    async def acquire_lock(self, lock_name: str, ttl_seconds: int = 45) -> bool:
        """
        Acquires a distributed lock with TTL expiration.
        Returns True if lock was acquired, False if already held.
        """
        key = f"lock:{lock_name}"
        if self._upstash_client:
            try:
                cmd = ["SET", key, "LOCKED", "EX", str(ttl_seconds), "NX"]
                async with httpx.AsyncClient(timeout=self._upstash_client.timeout) as client:
                    resp = await client.post(self._upstash_client.url, headers=self._upstash_client.headers, json=cmd)
                    if resp.status_code == 200:
                        data = resp.json()
                        return data.get("result") in ["OK", True, 1]
            except Exception as err:
                logger.warning(f"Upstash Redis lock acquisition failed for '{lock_name}' ({err}). Using in-memory lock.")
        # Local in-memory lock
        if await self._memory_cache.exists(key):
            return False
        await self._memory_cache.set(key, "LOCKED", ttl_seconds=ttl_seconds)
        return True

    async def release_lock(self, lock_name: str) -> bool:
        """Releases a previously acquired distributed lock."""
        key = f"lock:{lock_name}"
        return await self.delete(key)


    async def check_health(self) -> Dict[str, Any]:
        """
        Operational health check for Redis/Cache subsystem.
        Exposes NO credentials, tokens, or private URLs.
        """
        start_t = time.perf_counter()
        if not self._upstash_client:
            return {
                "status": "healthy",
                "reachable": True,
                "backend": "in_memory_fallback",
                "mode": "LOCAL_MEMORY",
                "latency_ms": 0.1
            }

        try:
            is_pong = await self._upstash_client.ping()
            latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
            if is_pong:
                return {
                    "status": "healthy",
                    "reachable": True,
                    "backend": "upstash_redis_rest",
                    "mode": "CLOUD_REST",
                    "latency_ms": latency_ms
                }
            else:
                return {
                    "status": "degraded",
                    "reachable": False,
                    "backend": "upstash_redis_rest",
                    "mode": "FALLBACK_TO_MEMORY",
                    "latency_ms": latency_ms,
                    "error": "Ping returned non-PONG result"
                }
        except Exception as err:
            latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
            logger.warning(f"Redis health check failed ({err}). Operating in resilient in-memory mode.")
            return {
                "status": "degraded",
                "reachable": False,
                "backend": "in_memory_fallback",
                "mode": "FALLBACK_TO_MEMORY",
                "latency_ms": latency_ms,
                "error": "Redis connection timed out or unreachable"
            }


class RateLimiter:
    """
    Non-blocking, token/window rate limiter using Redis atomic increments with fallback.
    """

    def __init__(self, redis_service: RedisService):
        self.redis = redis_service

    async def check_rate_limit(
        self,
        identifier: str,
        action: str,
        max_requests: int = 60,
        window_seconds: int = 60
    ) -> Tuple[bool, int, int]:
        """
        Checks rate limit for an identifier + action pair.
        Returns: (is_allowed: bool, current_count: int, retry_after: int)
        """
        key = f"ratelimit:{action}:{identifier}"
        try:
            current_count = await self.redis.increment(key, amount=1, ttl_seconds=window_seconds)
            is_allowed = current_count <= max_requests
            retry_after = window_seconds if not is_allowed else 0
            return is_allowed, current_count, retry_after
        except Exception as err:
            logger.warning(f"RateLimiter evaluation failed for '{key}' ({err}). Allowing request.")
            return True, 1, 0


# Singleton global instance
redis_service = RedisService()
rate_limiter = RateLimiter(redis_service)
