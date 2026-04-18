"""缓存模块测试。"""

import time

from code_review.infrastructure.cache import TTLCache


class TestTTLCache:
    def test_set_and_get(self):
        cache = TTLCache()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing_key(self):
        cache = TTLCache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiration(self):
        cache = TTLCache(default_ttl=1)
        cache.set("key1", "value1", ttl=1)
        assert cache.get("key1") == "value1"
        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_delete(self):
        cache = TTLCache()
        cache.set("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_exists(self):
        cache = TTLCache()
        cache.set("key1", "value1")
        assert cache.exists("key1")
        assert not cache.exists("key2")

    def test_max_size_eviction(self):
        cache = TTLCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # 应触发淘汰
        assert cache.get("d") == 4

    def test_clear(self):
        cache = TTLCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_dedup_cache_usage(self):
        from code_review.infrastructure.cache import event_dedup_cache
        event_id = "test-event-123"
        assert not event_dedup_cache.exists(event_id)
        event_dedup_cache.set(event_id, True, ttl=60)
        assert event_dedup_cache.exists(event_id)
        # 清理
        event_dedup_cache.delete(event_id)
