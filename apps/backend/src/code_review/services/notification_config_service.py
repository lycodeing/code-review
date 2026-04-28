"""通知渠道配置 CRUD 服务 + 缓存。"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from code_review.infrastructure.config_crypto import encrypt, decrypt
from code_review.models.db import (
    NotificationConfig,
    PlatformNotificationBinding,
    PlatformConfig,
)

logger = logging.getLogger(__name__)

# 内存缓存（channel -> NotificationConfig）
_cache: dict[str, tuple[float, NotificationConfig]] = {}
_CACHE_TTL = 300.0


def _cache_key(channel: str) -> str:
    return f"notification:{channel}"


def _is_cache_valid(entry: tuple[float, object], ttl: float = _CACHE_TTL) -> bool:
    import time
    return (time.monotonic() - entry[0]) < ttl


class NotificationConfigService:
    """通知渠道配置 CRUD 服务。"""

    def __init__(self, session: AsyncSession, secret_key: str = ""):
        self._session = session
        self._secret_key = secret_key

    # ---- 读取 ----

    async def get_by_channel(self, channel: str) -> NotificationConfig | None:
        """根据渠道标识查询配置（走缓存）。"""
        key = _cache_key(channel)
        entry = _cache.get(key)
        if entry and _is_cache_valid(entry):
            return entry[1]

        stmt = select(NotificationConfig).where(NotificationConfig.channel == channel)
        result = await self._session.execute(stmt)
        nc = result.scalar_one_or_none()
        if nc:
            self._decrypt_sensitive(nc)
            _cache[key] = (self._now(), nc)
        return nc

    async def get_all(self) -> list[NotificationConfig]:
        """查询所有通知渠道配置。"""
        stmt = select(NotificationConfig).order_by(NotificationConfig.channel)
        result = await self._session.execute(stmt)
        configs = list(result.scalars().all())
        for nc in configs:
            self._decrypt_sensitive(nc)
        return configs

    async def get_enabled(self) -> list[NotificationConfig]:
        """查询所有已启用的通知渠道。"""
        stmt = select(NotificationConfig).where(NotificationConfig.enabled == True)  # noqa: E712
        result = await self._session.execute(stmt)
        configs = list(result.scalars().all())
        for nc in configs:
            self._decrypt_sensitive(nc)
        return configs

    async def get_enabled_for_platform(self, platform: str) -> list[NotificationConfig]:
        """查询指定平台绑定的已启用通知渠道。"""
        stmt = (
            select(NotificationConfig)
            .join(
                PlatformNotificationBinding,
                PlatformNotificationBinding.notification_id == NotificationConfig.id,
            )
            .join(
                PlatformConfig,
                PlatformConfig.id == PlatformNotificationBinding.platform_id,
            )
            .where(
                PlatformConfig.platform == platform,
                PlatformNotificationBinding.enabled == True,  # noqa: E712
                NotificationConfig.enabled == True,  # noqa: E712
            )
        )
        result = await self._session.execute(stmt)
        configs = list(result.scalars().all())
        for nc in configs:
            self._decrypt_sensitive(nc)
        return configs

    # ---- 写入 ----

    async def create(
        self,
        channel: str,
        enabled: bool = False,
        webhook_url: str = "",
        secret: str = "",
        at_mobiles: str = "",
        description: str = "",
    ) -> NotificationConfig:
        """创建通知渠道配置。"""
        nc = NotificationConfig(
            channel=channel,
            enabled=enabled,
            webhook_url=webhook_url,
            secret=encrypt(secret, self._secret_key) if secret else "",
            at_mobiles=at_mobiles,
            description=description,
        )
        self._session.add(nc)
        await self._session.commit()
        await self._session.refresh(nc)
        self._decrypt_sensitive(nc)
        self._invalidate_cache(channel)
        return nc

    async def update(self, channel: str, **fields) -> NotificationConfig | None:
        """更新通知渠道配置。"""
        nc = await self._get_raw(channel)
        if nc is None:
            return None

        for key, value in fields.items():
            if value is None:
                continue
            if key == "secret" and value:
                value = encrypt(value, self._secret_key)
            setattr(nc, key, value)

        nc.updated_at = datetime.now(timezone.utc)
        await self._session.commit()
        await self._session.refresh(nc)
        self._decrypt_sensitive(nc)
        self._invalidate_cache(channel)
        return nc

    async def delete(self, channel: str) -> bool:
        """删除通知渠道配置。"""
        nc = await self._get_raw(channel)
        if nc is None:
            return False
        await self._session.delete(nc)
        await self._session.commit()
        self._invalidate_cache(channel)
        return True

    async def batch_import(
        self, configs: list[dict], overwrite: bool = False
    ) -> dict:
        """批量导入通知渠道配置。"""
        imported = 0
        skipped = 0
        errors = []

        for cfg in configs:
            channel = cfg.get("channel", "")
            if not channel:
                errors.append("Missing 'channel' field")
                continue
            try:
                existing = await self._get_raw(channel)
                if existing:
                    if overwrite:
                        for key in ("webhook_url", "at_mobiles", "description"):
                            if key in cfg and cfg[key]:
                                setattr(existing, key, cfg[key])
                        if "secret" in cfg and cfg["secret"]:
                            existing.secret = encrypt(cfg["secret"], self._secret_key)
                        if "enabled" in cfg:
                            existing.enabled = cfg["enabled"]
                        existing.updated_at = datetime.now(timezone.utc)
                        imported += 1
                    else:
                        skipped += 1
                else:
                    nc = NotificationConfig(
                        channel=channel,
                        enabled=cfg.get("enabled", False),
                        webhook_url=cfg.get("webhook_url", ""),
                        secret=encrypt(cfg["secret"], self._secret_key) if cfg.get("secret") else "",
                        at_mobiles=cfg.get("at_mobiles", ""),
                        description=cfg.get("description", ""),
                    )
                    self._session.add(nc)
                    imported += 1
            except Exception as e:
                errors.append(f"{channel}: {e}")

        await self._session.commit()
        self._invalidate_all_cache()
        return {"imported": imported, "skipped": skipped, "errors": errors}

    # ---- 绑定管理 ----

    async def set_binding(
        self, platform: str, channel: str, enabled: bool = True
    ) -> PlatformNotificationBinding | None:
        """设置平台-通知渠道绑定。"""
        pc_stmt = select(PlatformConfig).where(PlatformConfig.platform == platform)
        nc_stmt = select(NotificationConfig).where(NotificationConfig.channel == channel)
        pc_result = await self._session.execute(pc_stmt)
        nc_result = await self._session.execute(nc_stmt)
        pc = pc_result.scalar_one_or_none()
        nc = nc_result.scalar_one_or_none()
        if not pc or not nc:
            return None

        bind_stmt = select(PlatformNotificationBinding).where(
            PlatformNotificationBinding.platform_id == pc.id,
            PlatformNotificationBinding.notification_id == nc.id,
        )
        bind_result = await self._session.execute(bind_stmt)
        binding = bind_result.scalar_one_or_none()

        if binding:
            binding.enabled = enabled
        else:
            binding = PlatformNotificationBinding(
                platform_id=pc.id,
                notification_id=nc.id,
                enabled=enabled,
            )
            self._session.add(binding)

        await self._session.commit()
        await self._session.refresh(binding)
        return binding

    # ---- 缓存 ----

    def _invalidate_cache(self, channel: str) -> None:
        _cache.pop(_cache_key(channel), None)

    @staticmethod
    def _invalidate_all_cache() -> None:
        _cache.clear()

    # ---- 内部 ----

    async def _get_raw(self, channel: str) -> NotificationConfig | None:
        stmt = select(NotificationConfig).where(NotificationConfig.channel == channel)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    def _decrypt_sensitive(self, nc: NotificationConfig) -> None:
        if nc.secret and self._secret_key:
            nc.secret = decrypt(nc.secret, self._secret_key)

    @staticmethod
    def _now() -> float:
        import time
        return time.monotonic()
