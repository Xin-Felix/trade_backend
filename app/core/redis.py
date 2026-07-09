"""Redis 客户端封装。

用于缓存实时行情等短时热数据，未配置 redis_url 时自动降级为内存缓存。
"""

import json
import threading
import time
from functools import lru_cache
from typing import Any

from app.core.config import settings


class _MemoryCache:
    """未配置 Redis 时的本地内存缓存（带 TTL）。"""

    def __init__(self):
        self._data: dict[str, tuple[Any, float]] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key not in self._data:
                return None
            value, expire_at = self._data[key]
            if time.time() > expire_at:
                del self._data[key]
                return None
            return value

    def set(self, key: str, value: Any, ex: int) -> None:
        with self._lock:
            self._data[key] = (value, time.time() + ex)


@lru_cache(maxsize=1)
def _get_memory_cache() -> _MemoryCache:
    return _MemoryCache()


class RedisClient:
    """统一缓存入口：优先 Redis，未配置则回退到本地内存缓存。"""

    def __init__(self) -> None:
        self._redis = None
        self._memory = _get_memory_cache()
        if settings.redis_url:
            import redis as redis_lib

            self._redis = redis_lib.from_url(settings.redis_url, decode_responses=True)

    def get(self, key: str) -> Any | None:
        if self._redis is not None:
            try:
                raw = self._redis.get(key)
                if raw:
                    return json.loads(raw)
            except Exception:
                pass
        return self._memory.get(key)

    def set(self, key: str, value: Any, ex: int = 60) -> None:
        payload = json.dumps(value, default=str)
        if self._redis is not None:
            try:
                self._redis.set(key, payload, ex=ex)
                return
            except Exception:
                pass
        self._memory.set(key, value, ex=ex)


# 全局缓存实例
redis_client = RedisClient()
