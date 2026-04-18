"""简单的进程内 TTL 缓存。"""

import time
import logging
from typing import Any

logger = logging.getLogger(__name__)


class TTLCache:
    """简单的键值 TTL 缓存，用于缓存平台 API 响应和去重。"""

    def __init__(self, default_ttl: int = 300, max_size: int = 1000):
        self._store: dict[str, tuple[Any, float]] = {}
        self._default_ttl = default_ttl
        self._max_size = max_size

    def get(self, key: str) -> Any | None:
        """获取缓存值，过期返回 None。"""
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """设置缓存值。"""
        self._evict_if_needed()
        expires_at = time.time() + (ttl or self._default_ttl)
        self._store[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def _evict_if_needed(self) -> None:
        """超过最大容量时清除过期和最旧的条目。"""
        if len(self._store) < self._max_size:
            return
        # 先清除过期条目
        now = time.time()
        expired = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]
        # 如果还超限，按 FIFO 删除
        if len(self._store) >= self._max_size:
            keys_to_remove = list(self._store.keys())[: len(self._store) - self._max_size + 1]
            for k in keys_to_remove:
                del self._store[k]

    def clear(self) -> None:
        self._store.clear()


# 全局缓存实例
event_dedup_cache = TTLCache(default_ttl=3600, max_size=10000)
api_response_cache = TTLCache(default_ttl=300, max_size=2000)
