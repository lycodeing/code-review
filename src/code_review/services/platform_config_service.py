"""平台配置 CRUD 服务 + 缓存 + 降级。"""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from code_review.infrastructure.config_crypto import encrypt, decrypt
from code_review.models.db import (
    PlatformConfig,
    PlatformNotificationBinding,
    NotificationConfig,
)

logger = logging.getLogger(__name__)

# 内存缓存（platform -> PlatformConfig），简单 TTL
_cache: dict[str, tuple[float, PlatformConfig]] = {}
_CACHE_TTL = 300.0  # 5 分钟


def _cache_key(platform: str) -> str:
    return f"platform:{platform}"


def _is_cache_valid(entry: tuple[float, Any], ttl: float = _CACHE_TTL) -> bool:
    import time
    return (time.monotonic() - entry[0]) < ttl


class PlatformConfigService:
    """平台配置 CRUD 服务。"""

    def __init__(self, session: AsyncSession, secret_key: str = ""):
        self._session = session
        self._secret_key = secret_key

    # ---- 读取 ----

    async def get_by_platform(self, platform: str) -> PlatformConfig | None:
        """根据平台标识查询配置（走缓存）。"""
        key = _cache_key(platform)
        entry = _cache.get(key)
        if entry and _is_cache_valid(entry):
            return entry[1]

        stmt = select(PlatformConfig).where(PlatformConfig.platform == platform)
        result = await self._session.execute(stmt)
        pc = result.scalar_one_or_none()
        if pc:
            self._decrypt_sensitive(pc)
            _cache[key] = (self._now(), pc)
        return pc

    async def get_all(self) -> list[PlatformConfig]:
        """查询所有平台配置。"""
        stmt = select(PlatformConfig).order_by(PlatformConfig.platform)
        result = await self._session.execute(stmt)
        configs = list(result.scalars().all())
        for pc in configs:
            self._decrypt_sensitive(pc)
        return configs

    async def get_by_platform_with_fallback(
        self,
        platform: str,
        env_token: str = "",
        env_api_url: str = "",
        env_webhook_secret: str = "",
    ) -> PlatformConfig | None:
        """优先 DB，空值降级到 env 参数。

        用于灰度迁移期间的双读模式。
        """
        pc = await self.get_by_platform(platform)
        if pc is None:
            # DB 无记录，构建临时对象
            pc = PlatformConfig(
                platform=platform,
                access_token=env_token,
                webhook_secret=env_webhook_secret,
                api_url=env_api_url,
                enabled=True,
            )
            return pc

        # DB 有记录但敏感字段为空时，降级到 env
        if not pc.access_token and env_token:
            pc.access_token = env_token
        if not pc.webhook_secret and env_webhook_secret:
            pc.webhook_secret = env_webhook_secret
        if not pc.api_url and env_api_url:
            pc.api_url = env_api_url
        return pc

    async def get_bound_notifications(self, platform: str) -> list[NotificationConfig]:
        """查询平台绑定的已启用通知渠道。"""
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
        notifications = list(result.scalars().all())
        for n in notifications:
            self._decrypt_notification_secret(n)
        return notifications

    # ---- 写入 ----

    async def create(
        self,
        platform: str,
        access_token: str = "",
        webhook_secret: str = "",
        api_url: str = "",
        enabled: bool = True,
        description: str = "",
    ) -> PlatformConfig:
        """创建平台配置。"""
        pc = PlatformConfig(
            platform=platform,
            access_token=encrypt(access_token, self._secret_key) if access_token else "",
            webhook_secret=encrypt(webhook_secret, self._secret_key) if webhook_secret else "",
            api_url=api_url,
            enabled=enabled,
            description=description,
        )
        self._session.add(pc)
        await self._session.commit()
        await self._session.refresh(pc)
        self._decrypt_sensitive(pc)
        self._invalidate_cache(platform)
        return pc

    async def update(self, platform: str, **fields) -> PlatformConfig | None:
        """更新平台配置（仅传入需要更新的字段）。"""
        pc = await self._get_raw(platform)
        if pc is None:
            return None

        for key, value in fields.items():
            if value is None:
                continue
            if key in ("access_token", "webhook_secret") and value:
                value = encrypt(value, self._secret_key)
            setattr(pc, key, value)

        pc.updated_at = datetime.utcnow()
        await self._session.commit()
        await self._session.refresh(pc)
        self._decrypt_sensitive(pc)
        self._invalidate_cache(platform)
        return pc

    async def delete(self, platform: str) -> bool:
        """删除平台配置。"""
        pc = await self._get_raw(platform)
        if pc is None:
            return False
        await self._session.delete(pc)
        await self._session.commit()
        self._invalidate_cache(platform)
        return True

    async def batch_import(
        self, configs: list[dict], overwrite: bool = False
    ) -> dict:
        """批量导入平台配置。"""
        imported = 0
        skipped = 0
        errors = []

        for cfg in configs:
            platform = cfg.get("platform", "")
            if not platform:
                errors.append("Missing 'platform' field")
                continue
            try:
                existing = await self._get_raw(platform)
                if existing:
                    if overwrite:
                        for key in ("access_token", "webhook_secret", "api_url", "description"):
                            if key in cfg and cfg[key]:
                                val = cfg[key]
                                if key in ("access_token", "webhook_secret"):
                                    val = encrypt(val, self._secret_key)
                                setattr(existing, key, val)
                        if "enabled" in cfg:
                            existing.enabled = cfg["enabled"]
                        existing.updated_at = datetime.utcnow()
                        imported += 1
                    else:
                        skipped += 1
                else:
                    pc = PlatformConfig(
                        platform=platform,
                        access_token=encrypt(cfg["access_token"], self._secret_key) if cfg.get("access_token") else "",
                        webhook_secret=encrypt(cfg["webhook_secret"], self._secret_key) if cfg.get("webhook_secret") else "",
                        api_url=cfg.get("api_url", ""),
                        enabled=cfg.get("enabled", True),
                        description=cfg.get("description", ""),
                    )
                    self._session.add(pc)
                    imported += 1
            except Exception as e:
                errors.append(f"{platform}: {e}")

        await self._session.commit()
        self._invalidate_all_cache()
        return {"imported": imported, "skipped": skipped, "errors": errors}

    # ---- 缓存 ----

    def _invalidate_cache(self, platform: str) -> None:
        _cache.pop(_cache_key(platform), None)

    @staticmethod
    def _invalidate_all_cache() -> None:
        _cache.clear()

    # ---- 内部 ----

    async def _get_raw(self, platform: str) -> PlatformConfig | None:
        """直接查 DB（不走缓存，不解密）。"""
        stmt = select(PlatformConfig).where(PlatformConfig.platform == platform)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    def _decrypt_sensitive(self, pc: PlatformConfig) -> None:
        """解密敏感字段。"""
        if pc.access_token and self._secret_key:
            pc.access_token = decrypt(pc.access_token, self._secret_key)
        if pc.webhook_secret and self._secret_key:
            pc.webhook_secret = decrypt(pc.webhook_secret, self._secret_key)

    @staticmethod
    def _decrypt_notification_secret(nc: NotificationConfig) -> None:
        """解密通知渠道密钥（由 NotificationConfigService 调用）。"""
        pass

    @staticmethod
    def _now() -> float:
        import time
        return time.monotonic()
