"""飞书机器人通知渠道。"""

import hashlib
import hmac
import base64
import time
import logging

import httpx

from code_review.core.notification import NotificationChannel, NotificationPayload
from code_review.models.config import FeishuConfig

logger = logging.getLogger(__name__)


class FeishuChannel(NotificationChannel):
    """飞书自定义机器人 Webhook 通知。"""

    def __init__(self, config: FeishuConfig):
        self._config = config
        self._webhook_url = config.webhook_url
        self._secret = config.secret

    @property
    def name(self) -> str:
        return "feishu"

    @property
    def enabled(self) -> bool:
        return self._config.enabled and bool(self._webhook_url)

    async def send(self, payload: NotificationPayload) -> bool:
        if not self.enabled:
            return False

        try:
            headers = {"Content-Type": "application/json"}
            body = self._build_message(payload)

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self._webhook_url, json=body, headers=headers
                )

            if resp.status_code == 200:
                result = resp.json()
                if result.get("code") == 0:
                    logger.info("Feishu notification sent for MR: %s", payload.mr_title)
                    return True
                logger.error("Feishu API error: %s", result.get("msg"))
            else:
                logger.error("Feishu HTTP error: %d", resp.status_code)

        except Exception as e:
            logger.error("Failed to send Feishu notification: %s", e)

        return False

    def _build_message(self, payload: NotificationPayload) -> dict:
        """构建飞书消息卡片。"""
        severity_emoji = {"critical": "🔴", "warning": "🟡", "suggestion": "🔵", "info": "ℹ️"}

        summary_section = (
            f"**项目**: {payload.project_name}\n"
            f"**MR**: [{payload.mr_title}]({payload.mr_url})\n"
            f"**作者**: {payload.mr_author}\n\n"
            f"{payload.summary}\n\n"
            f"🔴 严重: {payload.critical_count} | "
            f"🟡 警告: {payload.warning_count} | "
            f"🔵 建议: {payload.suggestion_count} | "
            f"ℹ️ 信息: {payload.info_count}"
        )

        if payload.detail_link:
            summary_section += f"\n\n[查看详情]({payload.detail_link})"

        message: dict = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"🔍 代码评审结果 - {payload.mr_title}"},
                    "template": "blue" if payload.critical_count == 0 else "red",
                },
                "elements": [
                    {"tag": "markdown", "content": summary_section},
                ],
            },
        }

        # 如果配置了签名密钥，添加签名
        if self._secret:
            timestamp = str(int(time.time()))
            sign = self._gen_sign(timestamp)
            message["timestamp"] = timestamp
            message["sign"] = sign

        return message

    def _gen_sign(self, timestamp: str) -> str:
        """生成飞书 Webhook 签名。"""
        string_to_sign = f"{timestamp}\n{self._secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(hmac_code).decode("utf-8")

    async def health_check(self) -> bool:
        return self.enabled
