"""通知渠道管理器 - 统一调度所有通知渠道。"""

import logging
from uuid import UUID

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
        # 存储 (channel实例, notification_config_id) 元组，以便 notify_all 时查找模板
        self._channels: list[tuple[NotificationChannel, UUID | None]] = []

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
                    self._channels.append((channel, cfg.id))
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
                        self._channels.append((channel, None))
                        logger.info("Notification channel enabled from ENV: %s", channel_name)

    def init_channels_sync(self) -> None:
        """同步初始化通知渠道（使用 env 配置，用于 Worker 等无 DB 上下文场景）。"""
        self._channels.clear()
        self._init_channels_from_env()

    async def notify_all(
        self,
        payload: NotificationPayload,
        project_id: UUID | None = None,
        session_factory=None,
        secret_key: str = "",
    ) -> dict[str, bool]:
        """向所有已启用渠道发送通知。

        发送前按三级优先级解析通知模板并渲染，结果写入 payload 的
        rendered_title / rendered_body 字段供渠道使用。

        Args:
            payload: 通知内容载荷。
            project_id: 项目 UUID，有值时尝试解析项目级模板绑定。
            session_factory: 数据库 session 工厂，有值时从 DB 解析模板。
            secret_key: 解密密钥（暂时保留签名，供未来扩展）。

        Returns:
            各渠道发送结果 {channel_name: success}。
        """
        results = {}
        for channel, notification_id in self._channels:
            # 尝试解析并渲染模板，写入 payload 临时字段
            rendered_payload = await self._render_payload(
                payload, project_id, notification_id, session_factory,
            )
            try:
                success = await channel.send(rendered_payload)
                results[channel.name] = success
            except Exception as e:
                logger.error("Notification channel %s failed: %s", channel.name, e)
                results[channel.name] = False
        return results

    async def _render_payload(
        self,
        payload: NotificationPayload,
        project_id: UUID | None,
        notification_id: UUID | None,
        session_factory,
    ) -> NotificationPayload:
        """解析模板并渲染，返回附有 rendered_title/rendered_body 的新 payload。

        无法解析或渲染失败时返回原始 payload（渠道使用硬编码兜底逻辑）。
        """
        if session_factory is None or project_id is None or notification_id is None:
            return payload

        try:
            from code_review.services.notification_template_service import NotificationTemplateService
            from code_review.infrastructure.notification_renderer import NotificationRenderer

            async with session_factory() as session:
                svc = NotificationTemplateService(session)
                tpl = await svc.resolve_template(project_id, notification_id)

            if tpl is None:
                return payload

            rendered_title, rendered_body = NotificationRenderer.render(
                tpl.title_template, tpl.body_template, payload
            )
            import dataclasses
            return dataclasses.replace(
                payload,
                rendered_title=rendered_title,
                rendered_body=rendered_body,
            )
        except Exception as e:
            logger.warning("模板渲染失败，使用硬编码兜底: %s", e)
            return payload

    async def health_check(self) -> dict[str, bool]:
        """检查所有渠道健康状态。"""
        return {
            channel.name: await channel.health_check()
            for channel, _ in self._channels
        }
