"""通知渠道管理器 - 统一调度所有通知渠道。"""

import logging

from code_review.core.notification import NotificationChannel, NotificationPayload
from code_review.infrastructure.notification_feishu import FeishuChannel
from code_review.infrastructure.notification_dingtalk import DingTalkChannel
from code_review.models.config import AppConfig

logger = logging.getLogger(__name__)

# 通知渠道类注册表
CHANNEL_REGISTRY: dict[str, type[NotificationChannel]] = {
    "feishu": FeishuChannel,
    "dingtalk": DingTalkChannel,
}


class NotificationManager:
    """统一管理所有通知渠道，支持按配置启用/禁用。"""

    def __init__(self, config: AppConfig):
        """初始化（保留 env 配置作为降级）。"""
        self._config = config
        self._channels: list[NotificationChannel] = []

    async def init_channels_from_db(self, session_factory, secret_key: str, platform: str = "") -> None:
        """从数据库加载通知渠道配置。

        Args:
            session_factory: SQLAlchemy async session factory。
            secret_key: 用于解密敏感字段的密钥。
            platform: 指定平台时只加载该平台绑定的渠道，为空则加载所有已启用渠道。
        """
        from code_review.services.notification_config_service import NotificationConfigService

        self._channels.clear()

        async with session_factory() as session:
            svc = NotificationConfigService(session, secret_key)
            if platform:
                configs = await svc.get_enabled_for_platform(platform)
            else:
                configs = await svc.get_enabled()

        for cfg in configs:
            channel_cls = CHANNEL_REGISTRY.get(cfg.channel)
            if channel_cls:
                channel = channel_cls(cfg)
                if channel.enabled:
                    self._channels.append(channel)
                    logger.info("Notification channel enabled from DB: %s", channel.name)

        # 如果 DB 中没有启用的渠道，降级到 env 配置
        if not self._channels:
            self._init_channels_from_env()

    def _init_channels_from_env(self) -> None:
        """降级：从环境变量配置初始化通知渠道。"""
        env_configs = [
            ("feishu", self._config.feishu),
            ("dingtalk", self._config.dingtalk),
        ]
        for channel_name, cfg in env_configs:
            if cfg.enabled:
                channel_cls = CHANNEL_REGISTRY.get(channel_name)
                if channel_cls:
                    channel = channel_cls(cfg)
                    if channel.enabled:
                        self._channels.append(channel)
                        logger.info("Notification channel enabled from ENV: %s", channel_name)

    def init_channels_sync(self) -> None:
        """同步初始化通知渠道（使用 env 配置，用于 Worker 等无 DB 上下文场景）。"""
        self._channels.clear()
        self._init_channels_from_env()

    async def notify_all(self, payload: NotificationPayload) -> dict[str, bool]:
        """向所有已启用渠道发送通知。

        Returns:
            各渠道发送结果 {channel_name: success}。
        """
        results = {}
        for channel in self._channels:
            try:
                success = await channel.send(payload)
                results[channel.name] = success
            except Exception as e:
                logger.error(
                    "Notification channel %s failed: %s", channel.name, e
                )
                results[channel.name] = False
        return results

    async def health_check(self) -> dict[str, bool]:
        """检查所有渠道健康状态。"""
        return {
            channel.name: await channel.health_check()
            for channel in self._channels
        }
