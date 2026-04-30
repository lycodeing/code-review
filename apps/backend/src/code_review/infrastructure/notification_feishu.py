"""飞书机器人通知渠道。"""

import base64
import hashlib
import hmac
import logging
import time

import httpx

from code_review.core.notification import NotificationChannel, NotificationPayload, NotificationResult

logger = logging.getLogger(__name__)


class FeishuChannel(NotificationChannel):
    """飞书自定义机器人 Webhook 通知。"""

    def __init__(self, config, timeout: int = 30):
        self._enabled = getattr(config, "enabled", False)
        self._webhook_url = getattr(config, "webhook_url", "")
        self._secret = getattr(config, "secret", "")
        self._timeout = None if timeout == -1 else timeout

    @property
    def name(self) -> str:
        return "feishu"

    @property
    def enabled(self) -> bool:
        return self._enabled and bool(self._webhook_url)

    async def send(self, payload: NotificationPayload) -> NotificationResult:
        req_headers = {"Content-Type": "application/json"}

        if not self.enabled:
            return NotificationResult(
                success=False,
                provider="feishu",
                url=self._webhook_url,
                request_headers=req_headers,
                error_message="渠道未启用或 Webhook URL 未配置",
            )

        t0 = time.perf_counter()
        body: dict = {}
        try:
            body = self._build_message(payload)
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(self._webhook_url, json=body, headers=req_headers)

            duration_ms = int((time.perf_counter() - t0) * 1000)
            resp_body: dict = {}
            try:
                resp_body = resp.json()
            except Exception:
                pass

            if resp.status_code == 200 and resp_body.get("code") == 0:
                logger.info("Feishu notification sent for MR: %s", payload.mr_title)
                return NotificationResult(
                    success=True,
                    provider="feishu",
                    url=self._webhook_url,
                    request_headers=req_headers,
                    request_body=body,
                    response_status=resp.status_code,
                    response_body=resp_body,
                    duration_ms=duration_ms,
                )

            error_msg = resp_body.get("msg") or f"HTTP {resp.status_code}"
            logger.error("Feishu send failed: %s", error_msg)
            return NotificationResult(
                success=False,
                provider="feishu",
                url=self._webhook_url,
                request_headers=req_headers,
                request_body=body,
                response_status=resp.status_code,
                response_body=resp_body,
                error_message=error_msg,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            logger.error("Failed to send Feishu notification: %s", e)
            return NotificationResult(
                success=False,
                provider="feishu",
                url=self._webhook_url,
                request_headers=req_headers,
                request_body=body,
                error_message=str(e),
                duration_ms=duration_ms,
            )

    def _build_message(self, payload: NotificationPayload) -> dict:
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

        if self._secret:
            timestamp = str(int(time.time()))
            sign = self._gen_sign(timestamp)
            message["timestamp"] = timestamp
            message["sign"] = sign

        return message

    def _gen_sign(self, timestamp: str) -> str:
        string_to_sign = f"{timestamp}\n{self._secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(hmac_code).decode("utf-8")

    async def health_check(self) -> bool:
        return self.enabled
