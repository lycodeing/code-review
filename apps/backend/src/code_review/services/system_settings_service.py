"""系统配置服务 — 带 TTL 内存缓存的通用 key-value 读写。"""

import logging
import time

from sqlalchemy import func, select, update, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from code_review.models.db import SystemSetting

logger = logging.getLogger(__name__)

_CACHE_TTL = 60  # 缓存有效期（秒）

# 模块级缓存：key -> (expire_at, value_str)
_cache: dict[str, tuple[float, str]] = {}


class SystemSettingsService:
    """系统配置服务。"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_all(self) -> list[SystemSetting]:
        """获取全部配置，按 category + sort_order 排序。"""
        stmt = select(SystemSetting).order_by(SystemSetting.category, SystemSetting.sort_order)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_category(self, category: str) -> list[SystemSetting]:
        """按分类获取配置。"""
        stmt = (
            select(SystemSetting)
            .where(SystemSetting.category == category)
            .order_by(SystemSetting.sort_order)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_categories(self) -> list[dict[str, str | int]]:
        """获取所有分类及其配置项数量。"""
        stmt = (
            select(SystemSetting.category, func.count(SystemSetting.key))
            .group_by(SystemSetting.category)
            .order_by(SystemSetting.category)
        )
        result = await self._session.execute(stmt)
        return [{"key": row[0], "count": row[1]} for row in result.all()]

    async def get_value(self, key: str, default: str | None = None) -> str | None:
        """获取单个配置值（走缓存）。"""
        now = time.monotonic()
        cached = _cache.get(key)
        if cached and cached[0] > now:
            return cached[1]

        stmt = select(SystemSetting.value).where(SystemSetting.key == key)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is not None:
            _cache[key] = (now + _CACHE_TTL, row)
            return row
        return default

    async def get_int(self, key: str, default: int = 0) -> int:
        """获取整数值，转换失败返回 default。"""
        raw = await self.get_value(key)
        if raw is None:
            return default
        try:
            return int(raw)
        except (ValueError, TypeError):
            return default

    async def get_bool(self, key: str, default: bool = False) -> bool:
        """获取布尔值。支持 true/false/1/0/yes/no。"""
        raw = await self.get_value(key)
        if raw is None:
            return default
        return raw.lower() in ("true", "1", "yes", "on")

    async def get_string(self, key: str, default: str = "") -> str:
        """获取字符串值。"""
        raw = await self.get_value(key)
        return raw if raw is not None else default

    async def update_batch(self, items: list[dict[str, str]]) -> list[SystemSetting]:
        """批量更新配置值，立即清缓存。"""
        updated_keys: list[str] = []
        for item in items:
            stmt = (
                update(SystemSetting)
                .where(SystemSetting.key == item["key"])
                .values(value=item["value"])
            )
            await self._session.execute(stmt)
            updated_keys.append(item["key"])

        await self._session.commit()

        for k in updated_keys:
            _cache.pop(k, None)

        logger.info("系统配置已更新: %s", updated_keys)
        return await self.get_all()

    @staticmethod
    def invalidate_cache() -> None:
        """清除全部缓存。"""
        _cache.clear()
