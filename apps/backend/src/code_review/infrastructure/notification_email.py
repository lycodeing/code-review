"""邮件通知渠道（预留接口）。"""

import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import aiosmtplib

from code_review.core.notification import NotificationChannel, NotificationPayload
from code_review.models.config import EmailConfig

logger = logging.getLogger(__name__)


class EmailChannel(NotificationChannel):
    """邮件通知渠道。"""

    def __init__(self, config: EmailConfig):
        self._config = config

    @property
    def name(self) -> str:
        return "email"

    @property
    def enabled(self) -> bool:
        return self._config.enabled and bool(self._config.smtp_host)

    async def send(self, payload: NotificationPayload) -> bool:
        if not self.enabled:
            return False

        try:
            message = self._build_message(payload)

            await aiosmtplib.send(
                message,
                hostname=self._config.smtp_host,
                port=self._config.smtp_port,
                username=self._config.smtp_user or None,
                password=self._config.smtp_password or None,
                use_tls=True,
            )

            logger.info("Email notification sent for MR: %s", payload.mr_title)
            return True

        except Exception as e:
            logger.error("Failed to send email notification: %s", e)
            return False

    def _build_message(self, payload: NotificationPayload) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"代码评审结果 - {payload.mr_title}"
        msg["From"] = self._config.from_addr
        msg["To"] = ", ".join(self._config.to_addrs)

        text = (
            f"代码评审结果\n\n"
            f"项目: {payload.project_name}\n"
            f"MR: {payload.mr_title}\n"
            f"作者: {payload.mr_author}\n"
            f"链接: {payload.mr_url}\n\n"
            f"摘要: {payload.summary}\n\n"
            f"严重: {payload.critical_count} | "
            f"警告: {payload.warning_count} | "
            f"建议: {payload.suggestion_count} | "
            f"信息: {payload.info_count}"
        )

        html = f"""
        <h2>🔍 代码评审结果</h2>
        <p><strong>项目</strong>: {payload.project_name}</p>
        <p><strong>MR</strong>: <a href="{payload.mr_url}">{payload.mr_title}</a></p>
        <p><strong>作者</strong>: {payload.mr_author}</p>
        <hr>
        <p>{payload.summary}</p>
        <p>
            🔴 严重: <strong>{payload.critical_count}</strong> |
            🟡 警告: <strong>{payload.warning_count}</strong> |
            🔵 建议: <strong>{payload.suggestion_count}</strong> |
            ℹ️ 信息: <strong>{payload.info_count}</strong>
        </p>
        """

        msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))
        return msg

    async def health_check(self) -> bool:
        return self.enabled
