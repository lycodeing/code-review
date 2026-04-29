"""通知渠道管理器 - 统一调度所有通知渠道。"""

import dataclasses
import logging
from uuid import UUID

from code_review.core.notification import NotificationChannel, NotificationPayload
from code_review.infrastructure.notification_feishu import FeishuChannel
from code_review.infrastructure.notification_dingtalk import DingTalkChannel
from code_review.infrastructure.notification_email import EmailChannel
from code_review.models.config import AppConfig, EmailConfig

logger = logging.getLogger(__name__)

# 通知渠道类注册表
CHANNEL_REGISTRY: dict[str, type[NotificationChannel]] = {
    "feishu": FeishuChannel,
    "dingtalk": DingTalkChannel,
    "email": EmailChannel,
}


async def _save_notification_log(session_factory, task_id: UUID, result) -> None:
    """将通知发送结果写入 api_call_logs 表。"""
    try:
        from code_review.models.db import ApiCallLog
        async with session_factory() as session:
            log = ApiCallLog(
                task_id=task_id,
                call_type=ApiCallLog.CallType.NOTIFICATION,
                provider=result.provider,
                method="POST",
                url=result.url,
                request_headers=result.request_headers,
                request_body=result.request_body,
                response_status=result.response_status,
                response_body=result.response_body,
                status=ApiCallLog.CallStatus.SUCCESS if result.success else ApiCallLog.CallStatus.FAILED,
                error_message=result.error_message,
                duration_ms=result.duration_ms,
            )
            session.add(log)
            await session.commit()
    except Exception as e:
        logger.warning("记录通知调用日志失败: %s", e)


class NotificationManager:
    """统一管理所有通知渠道，支持按配置启用/禁用。"""

    def __init__(self, config: AppConfig):
        self._config = config
        self._channels: list[tuple[NotificationChannel, UUID | None]] = []

    async def init_channels_from_db(self, session_factory, secret_key: str, platform: str = "") -> None:
        """从数据库加载通知渠道配置。"""
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
                # Email 渠道从 extra_config 构造配置
                if cfg.channel == "email" and cfg.extra_config:
                    channel = self._create_email_channel(cfg)
                else:
                    channel = channel_cls(cfg)
                if channel and channel.enabled:
                    self._channels.append((channel, cfg.id))
                    logger.info("Notification channel enabled from DB: %s", channel.name)

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
        """同步初始化通知渠道（env 配置）。"""
        self._channels.clear()
        self._init_channels_from_env()

    @staticmethod
    def _create_email_channel(cfg) -> EmailChannel | None:
        """从数据库 NotificationConfig 的 extra_config 构造 EmailChannel。"""
        try:
            extra = cfg.extra_config or {}
            email_cfg = EmailConfig(
                enabled=cfg.enabled,
                smtp_host=extra.get("smtp_host", ""),
                smtp_port=extra.get("smtp_port", 587),
                smtp_user=extra.get("smtp_user", ""),
                smtp_password=cfg.secret or extra.get("smtp_password", ""),
                from_addr=extra.get("from_addr", ""),
                to_addrs=extra.get("to_addrs", []),
            )
            return EmailChannel(email_cfg)
        except Exception as e:
            logger.warning("构造 Email 渠道失败: %s", e)
            return None

    async def notify_all(
        self,
        payload: NotificationPayload,
        project_id: UUID | None = None,
        task_id: UUID | None = None,
        session_factory=None,
        project_config: dict | None = None,
    ) -> dict[str, bool]:
        """向所有已启用渠道发送通知，并将结果写入 api_call_logs。

        Args:
            payload: 通知内容载荷。
            project_id: 项目 UUID，有值时尝试解析项目级模板绑定。
            task_id: 评审任务 UUID，有值时将发送记录写入 api_call_logs。
            session_factory: 数据库 session 工厂。
            project_config: 项目配置 JSON，含 notification_min_severity 等过滤规则。

        Returns:
            各渠道发送结果 {channel_name: success}。
        """
        # 严重程度过滤
        if not self._should_notify(payload, project_config):
            logger.info("通知被过滤：未达到最小严重程度阈值")
            return {}
        results = {}
        for channel, notification_id in self._channels:
            rendered_payload = await self._render_payload(
                payload, project_id, notification_id, session_factory,
            )
            try:
                result = await channel.send(rendered_payload)
                results[channel.name] = result.success
            except Exception as e:
                logger.error("Notification channel %s failed: %s", channel.name, e)
                results[channel.name] = False
                result = None

            if task_id is not None and session_factory is not None and result is not None:
                await _save_notification_log(session_factory, task_id, result)

        return results

    async def _render_payload(
        self,
        payload: NotificationPayload,
        project_id: UUID | None,
        notification_id: UUID | None,
        session_factory,
    ) -> NotificationPayload:
        """解析模板并渲染，返回附有 rendered_title/rendered_body 的新 payload。"""
        if session_factory is None or project_id is None or notification_id is None:
            return payload

        try:
            from code_review.services.notification_template_service import NotificationTemplateService
            from code_review.infrastructure.notification_renderer import NotificationRenderer

            async with session_factory() as session:
                svc = NotificationTemplateService(session)
                tpl = await svc.resolve_template(project_id, notification_id)
                if tpl is None:
                    logger.warning(
                        "未找到通知模板（project=%s, notification=%s），跳过通知发送",
                        project_id, notification_id,
                    )
                    return payload
                tpl_name = tpl.name
                title_template = tpl.title_template
                body_template = tpl.body_template

            rendered_title, rendered_body = NotificationRenderer.render(
                title_template, body_template, payload
            )
            logger.info("使用自定义模板渲染通知: %s", tpl_name)
            return dataclasses.replace(
                payload,
                rendered_title=rendered_title,
                rendered_body=rendered_body,
            )
        except Exception as e:
            logger.warning("模板渲染失败: %s", e)
            return payload

    async def health_check(self) -> dict[str, bool]:
        """检查所有渠道健康状态。"""
        return {
            channel.name: await channel.health_check()
            for channel, _ in self._channels
        }

    @staticmethod
    def _should_notify(payload: NotificationPayload, project_config: dict | None) -> bool:
        """检查评审结果的严重程度是否达到通知阈值。

        配置格式（在 Project.config JSON 中）：
        {
            "notification_min_severity": "warning"  // info / suggestion / warning / critical
        }
        默认值为 "info"（所有评审都发送通知）。
        """
        severity_order = {"critical": 4, "warning": 3, "suggestion": 2, "info": 1}
        min_severity = (project_config or {}).get("notification_min_severity", "info")
        min_level = severity_order.get(min_severity, 1)

        # 计算本次评审中的最高严重程度
        severity_counts = {
            "critical": payload.critical_count,
            "warning": payload.warning_count,
            "suggestion": payload.suggestion_count,
            "info": payload.info_count,
        }
        max_level = max(
            (severity_order.get(s, 0) for s, c in severity_counts.items() if c > 0),
            default=0,
        )
        return max_level >= min_level
