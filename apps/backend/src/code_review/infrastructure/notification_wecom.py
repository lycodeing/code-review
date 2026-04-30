"""企业微信机器人通知渠道。"""

import logging
import time

import httpx

from code_review.core.notification import NotificationChannel, NotificationPayload, NotificationResult

logger = logging.getLogger(__name__)

_MAX_CONTENT_LENGTH = 4096


def _render_markdown(payload: NotificationPayload) -> str:
    """渲染企业微信 Markdown 消息内容。"""
    parts = [f"### {payload.project_name} 评审通知\n"]

    parts.append(f"> **MR:** [{payload.mr_title}]({payload.mr_url})")
    parts.append(f"> **作者:** {payload.mr_author}")

    if payload.critical_count > 0 or payload.warning_count > 0:
        stats = []
        if payload.critical_count > 0:
            stats.append(f"Critical: {payload.critical_count}")
        if payload.warning_count > 0:
            stats.append(f"Warning: {payload.warning_count}")
        if payload.suggestion_count > 0:
            stats.append(f"Suggestion: {payload.suggestion_count}")
        parts.append("> " + " | ".join(stats))

    if payload.summary:
        parts.append(f"\n> {payload.summary[:200]}")

    content = "\n".join(parts)
    if len(content.encode("utf-8")) > _MAX_CONTENT_LENGTH:
        content = content[:_MAX_CONTENT_LENGTH - 3] + "..."
    return content


class WeComChannel(NotificationChannel):
    """企业微信 Webhook 通知渠道。"""

    def __init__(self, config, timeout: int = 30):
        self._enabled = getattr(config, "enabled", False)
        self._webhook_url = getattr(config, "webhook_url", "")
        self._timeout = None if timeout == -1 else timeout

    @property
    def name(self) -> str:
        return "wecom"

    @property
    def enabled(self) -> bool:
        return self._enabled and bool(self._webhook_url)

    async def send(self, payload: NotificationPayload) -> NotificationResult:
        req_headers = {"Content-Type": "application/json"}

        if not self.enabled:
            return NotificationResult(
                success=False,
                provider="wecom",
                url=self._webhook_url,
                request_headers=req_headers,
                error_message="渠道未启用或 Webhook URL 未配置",
            )

        t0 = time.perf_counter()
        body: dict = {}
        try:
            content = payload.rendered_body if payload.rendered_body else _render_markdown(payload)
            body = {
                "msgtype": "markdown",
                "markdown": {"content": content},
            }
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(self._webhook_url, json=body, headers=req_headers)

            duration_ms = int((time.perf_counter() - t0) * 1000)
            resp_body: dict = {}
            try:
                resp_body = resp.json()
            except Exception:
                pass

            if resp.status_code == 200 and resp_body.get("errcode") == 0:
                logger.info("WeCom notification sent for MR: %s", payload.mr_title)
                return NotificationResult(
                    success=True,
                    provider="wecom",
                    url=self._webhook_url,
                    request_headers=req_headers,
                    request_body=body,
                    response_status=resp.status_code,
                    response_body=resp_body,
                    duration_ms=duration_ms,
                )

            error_msg = resp_body.get("errmsg", f"HTTP {resp.status_code}")
            logger.error("WeCom notification failed: %s", error_msg)
            return NotificationResult(
                success=False,
                provider="wecom",
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
            logger.error("WeCom notification error: %s", e)
            return NotificationResult(
                success=False,
                provider="wecom",
                url=self._webhook_url,
                request_headers=req_headers,
                request_body=body,
                error_message=str(e),
                duration_ms=duration_ms,
            )

    async def health_check(self) -> bool:
        if not self.enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(self._webhook_url)
                return resp.status_code == 200
        except Exception:
            return False
