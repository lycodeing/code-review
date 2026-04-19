"""钉钉机器人通知渠道。"""

import base64
import hashlib
import hmac
import logging
import re
import time
import urllib.parse

import httpx

from code_review.core.notification import NotificationChannel, NotificationPayload, NotificationResult

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"(access_token=)[^&]+")


def _sanitize_url(url: str) -> str:
    return _TOKEN_RE.sub(r"\1[REDACTED]", url)


class DingTalkChannel(NotificationChannel):
    """钉钉自定义机器人 Webhook 通知。"""

    def __init__(self, config):
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

    async def send(self, payload: NotificationPayload) -> NotificationResult:
        url = self._build_signed_url()
        sanitized_url = _sanitize_url(url)
        req_headers = {"Content-Type": "application/json"}

        if not self.enabled:
            return NotificationResult(
                success=False,
                provider="dingtalk",
                url=sanitized_url,
                request_headers=req_headers,
                error_message="渠道未启用或 Webhook URL 未配置",
            )

        t0 = time.perf_counter()
        body: dict = {}
        try:
            body = self._build_message(payload)
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json=body, headers=req_headers)

            duration_ms = int((time.perf_counter() - t0) * 1000)
            resp_body: dict = {}
            try:
                resp_body = resp.json()
            except Exception:
                pass

            if resp.status_code == 200 and resp_body.get("errcode") == 0:
                logger.info("DingTalk notification sent for MR: %s", payload.mr_title)
                return NotificationResult(
                    success=True,
                    provider="dingtalk",
                    url=sanitized_url,
                    request_headers=req_headers,
                    request_body=body,
                    response_status=resp.status_code,
                    response_body=resp_body,
                    duration_ms=duration_ms,
                )

            error_msg = resp_body.get("errmsg") or f"HTTP {resp.status_code}"
            logger.error("DingTalk send failed: %s", error_msg)
            return NotificationResult(
                success=False,
                provider="dingtalk",
                url=sanitized_url,
                request_headers=req_headers,
                request_body=body,
                response_status=resp.status_code,
                response_body=resp_body,
                error_message=error_msg,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            logger.error("Failed to send DingTalk notification: %s", e)
            return NotificationResult(
                success=False,
                provider="dingtalk",
                url=sanitized_url,
                request_headers=req_headers,
                request_body=body,
                error_message=str(e),
                duration_ms=duration_ms,
            )

    def _build_signed_url(self) -> str:
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
            url += f"&timestamp={timestamp}&sign={urllib.parse.quote(sign)}"
        return url

    def _build_message(self, payload: NotificationPayload) -> dict:
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
