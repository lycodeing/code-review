"""飞书机器人通知渠道。"""

import hashlib
import hmac
import base64
import time
import logging

import httpx

from code_review.core.notification import NotificationChannel, NotificationPayload

logger = logging.getLogger(__name__)


class FeishuChannel(NotificationChannel):
    """飞书自定义机器人 Webhook 通知。"""

    def __init__(self, config):
        """初始化飞书通知渠道。

        Args:
            config: NotificationConfig ORM 对象或兼容的 dict/namespace。
                    需要包含 enabled, webhook_url, secret 属性。
        """
        self._enabled = getattr(config, "enabled", False)
        self._webhook_url = getattr(config, "webhook_url", "")
        self._secret = getattr(config, "secret", "")

    @property
    def name(self) -> str:
        return "feishu"

    @property
    def enabled(self) -> bool:
        return self._enabled and bool(self._webhook_url)

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
        """构建飞书消息卡片，使用模板渲染结果。"""
        if not payload.rendered_title or not payload.rendered_body:
            raise ValueError("通知模板未渲染，请为该渠道配置通知模板")

        header_color = "red" if payload.critical_count > 0 else (
            "orange" if payload.warning_count > 0 else "blue"
        )

        message: dict = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": payload.rendered_title},
                    "template": header_color,
                },
                "elements": [
                    {"tag": "markdown", "content": payload.rendered_body},
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
