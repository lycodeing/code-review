"""钉钉机器人通知渠道。"""

import base64
import hashlib
import hmac
import logging
import time

import httpx

from code_review.core.notification import NotificationChannel, NotificationPayload

logger = logging.getLogger(__name__)


class DingTalkChannel(NotificationChannel):
    """钉钉自定义机器人 Webhook 通知。"""

    def __init__(self, config):
        """初始化钉钉通知渠道。

        Args:
            config: NotificationConfig ORM 对象或兼容的 dict/namespace。
                    需要包含 enabled, webhook_url, secret, at_mobiles 属性。
        """
        self._enabled = getattr(config, "enabled", False)
        self._webhook_url = getattr(config, "webhook_url", "")
        self._secret = getattr(config, "secret", "")
        self._at_mobiles = getattr(config, "at_mobiles", "")

    @property
    def name(self) -> str:
        return "dingtalk"

    @property
    def enabled(self) -> bool:
        return self._enabled and bool(self._webhook_url)

    async def send(self, payload: NotificationPayload) -> bool:
        if not self.enabled:
            return False

        try:
            url = self._build_signed_url()
            body = self._build_message(payload)

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    url, json=body, headers={"Content-Type": "application/json"}
                )

            if resp.status_code == 200:
                result = resp.json()
                if result.get("errcode") == 0:
                    logger.info("DingTalk notification sent for MR: %s", payload.mr_title)
                    return True
                logger.error("DingTalk API error: %s", result.get("errmsg"))
            else:
                logger.error("DingTalk HTTP error: %d", resp.status_code)

        except Exception as e:
            logger.error("Failed to send DingTalk notification: %s", e)

        return False

    def _build_signed_url(self) -> str:
        """构建带签名的 Webhook URL。"""
        url = self._webhook_url
        if self._secret:
            timestamp = str(round(time.time() * 1000))
            string_to_sign = f"{timestamp}\n{self._secret}"
            hmac_code = hmac.new(
                self._secret.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).digest()
            sign = base64.b64encode(hmac_code).decode("utf-8")
            import urllib.parse
            url += f"&timestamp={timestamp}&sign={urllib.parse.quote(sign)}"
        return url

    def _build_message(self, payload: NotificationPayload) -> dict:
        """构建钉钉 ActionCard 卡片消息，使用模板渲染结果。"""
        if not payload.rendered_title or not payload.rendered_body:
            raise ValueError("通知模板未渲染，请为该渠道配置通知模板")

        return {
            "msgtype": "actionCard",
            "actionCard": {
                "title": payload.rendered_title,
                "text": payload.rendered_body,
                "singleTitle": "查看 MR",
                "singleURL": payload.mr_url or payload.detail_link or "",
            },
        }

    async def health_check(self) -> bool:
        return self.enabled
