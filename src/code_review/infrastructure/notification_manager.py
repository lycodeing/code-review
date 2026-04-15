"""通知渠道管理器 - 统一调度所有通知渠道。"""

import logging

from code_review.core.notification import NotificationChannel, NotificationPayload
from code_review.infrastructure.notification_feishu import FeishuChannel
from code_review.infrastructure.notification_dingtalk import DingTalkChannel
from code_review.infrastructure.notification_email import EmailChannel
from code_review.models.config import AppConfig

logger = logging.getLogger(__name__)


class NotificationManager:
    """统一管理所有通知渠道，支持按配置启用/禁用。"""

    def __init__(self, config: AppConfig):
        self._channels: list[NotificationChannel] = []
        self._init_channels(config)

    def _init_channels(self, config: AppConfig) -> None:
        """根据配置初始化通知渠道。"""
        channel_classes = [FeishuChannel, DingTalkChannel, EmailChannel]
        configs_map = {
            "FeishuChannel": config.feishu,
            "DingTalkChannel": config.dingtalk,
            "EmailChannel": config.email,
        }

        for cls in channel_classes:
            cfg = configs_map.get(cls.__name__)
            if cfg:
                channel = cls(cfg)
                if channel.enabled:
                    self._channels.append(channel)
                    logger.info("Notification channel enabled: %s", channel.name)
                else:
                    logger.info("Notification channel disabled: %s", channel.name)

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
