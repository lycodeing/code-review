"""钉钉机器人通知渠道。"""

import base64
import hashlib
import hmac
import logging
import time

import httpx

from code_review.core.notification import NotificationChannel, NotificationPayload
from code_review.models.config import DingTalkConfig

logger = logging.getLogger(__name__)


class DingTalkChannel(NotificationChannel):
    """钉钉自定义机器人 Webhook 通知。"""

    def __init__(self, config: DingTalkConfig):
        self._config = config
        self._webhook_url = config.webhook_url
        self._secret = config.secret

    @property
    def name(self) -> str:
        return "dingtalk"

    @property
    def enabled(self) -> bool:
        return self._config.enabled and bool(self._webhook_url)

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
        """构建钉钉 Markdown 消息。"""
        text = (
            f"### 🔍 代码评审结果 - {payload.mr_title}\n\n"
            f"**项目**: {payload.project_name}  \n"
            f"**作者**: {payload.mr_author}  \n"
            f"**MR**: [{payload.mr_title}]({payload.mr_url})  \n\n"
            f"---  \n\n"
            f"{payload.summary}  \n\n"
            f"🔴 严重: **{payload.critical_count}** | "
            f"🟡 警告: **{payload.warning_count}** | "
            f"🔵 建议: **{payload.suggestion_count}** | "
            f"ℹ️ 信息: **{payload.info_count}**  \n"
        )

        if payload.detail_link:
            text += f"\n[查看详情]({payload.detail_link})"

        return {
            "msgtype": "markdown",
            "markdown": {
                "title": f"代码评审结果 - {payload.mr_title}",
                "text": text,
            },
        }

    async def health_check(self) -> bool:
        return self.enabled
