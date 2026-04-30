"""Slack Webhook 通知渠道。"""

import logging
import time

import httpx

from code_review.core.notification import NotificationChannel, NotificationPayload, NotificationResult

logger = logging.getLogger(__name__)

_MAX_BLOCKS = 50


def _build_blocks(payload: NotificationPayload) -> list[dict]:
    """构建 Slack Block Kit 消息。"""
    blocks: list[dict] = []

    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": f"{payload.project_name} 评审通知"},
    })

    if payload.summary:
        summary_text = payload.summary[:500]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*摘要:*\n{summary_text}"},
        })

    fields = [
        {"type": "mrkdwn", "text": f"*MR:*\n<{payload.mr_url}|{payload.mr_title}>"},
        {"type": "mrkdwn", "text": f"*作者:*\n{payload.mr_author}"},
    ]
    blocks.append({"type": "section", "fields": fields})

    stats_parts = []
    if payload.critical_count > 0:
        stats_parts.append(f"Critical: {payload.critical_count}")
    if payload.warning_count > 0:
        stats_parts.append(f"Warning: {payload.warning_count}")
    if payload.suggestion_count > 0:
        stats_parts.append(f"Suggestion: {payload.suggestion_count}")
    if payload.info_count > 0:
        stats_parts.append(f"Info: {payload.info_count}")

    if stats_parts:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": " | ".join(stats_parts)},
        })

    blocks.append({
        "type": "actions",
        "elements": [{
            "type": "button",
            "text": {"type": "plain_text", "text": "查看 MR"},
            "url": payload.mr_url,
        }],
    })

    return blocks[:_MAX_BLOCKS]


class SlackChannel(NotificationChannel):
    """Slack Webhook 通知渠道。"""

    def __init__(self, config, timeout: int = 30):
        self._enabled = getattr(config, "enabled", False)
        self._webhook_url = getattr(config, "webhook_url", "")
        self._timeout = None if timeout == -1 else timeout

    @property
    def name(self) -> str:
        return "slack"

    @property
    def enabled(self) -> bool:
        return self._enabled and bool(self._webhook_url)

    async def send(self, payload: NotificationPayload) -> NotificationResult:
        req_headers = {"Content-Type": "application/json"}

        if not self.enabled:
            return NotificationResult(
                success=False,
                provider="slack",
                url=self._webhook_url,
                request_headers=req_headers,
                error_message="渠道未启用或 Webhook URL 未配置",
            )

        t0 = time.perf_counter()
        body: dict = {}
        try:
            if payload.rendered_body:
                body = {"text": payload.rendered_body}
            else:
                body = {
                    "blocks": _build_blocks(payload),
                    "text": f"{payload.project_name} review completed: {payload.mr_title}",
                }

            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(self._webhook_url, json=body, headers=req_headers)

            duration_ms = int((time.perf_counter() - t0) * 1000)
            resp_body: dict = {}
            try:
                resp_body = resp.json()
            except Exception:
                pass

            if resp.status_code == 200 and resp_body.get("ok", True):
                logger.info("Slack notification sent for MR: %s", payload.mr_title)
                return NotificationResult(
                    success=True,
                    provider="slack",
                    url=self._webhook_url,
                    request_headers=req_headers,
                    request_body=body,
                    response_status=resp.status_code,
                    response_body=resp_body,
                    duration_ms=duration_ms,
                )

            error_msg = resp_body.get("error", f"HTTP {resp.status_code}")
            logger.error("Slack notification failed: %s", error_msg)
            return NotificationResult(
                success=False,
                provider="slack",
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
            logger.error("Slack notification error: %s", e)
            return NotificationResult(
                success=False,
                provider="slack",
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
                resp = await client.post(
                    self._webhook_url,
                    json={"text": "health check"},
                    headers={"Content-Type": "application/json"},
                )
                return resp.status_code == 200
        except Exception:
            return False
