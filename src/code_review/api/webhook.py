"""Webhook 接收端点。"""

import logging

from fastapi import APIRouter, Request, HTTPException, Header

from code_review.adapters.factory import create_adapter
from code_review.core.platform import PlatformType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(""),
    x_github_event: str = Header(""),
    x_github_delivery: str = Header(""),
):
    """GitHub Webhook 接收端点。"""
    config = request.app.state.config
    payload_bytes = await request.body()

    # 签名验证
    adapter = create_adapter(PlatformType.GITHUB, config)
    if not await adapter.verify_webhook_signature(payload_bytes, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 仅处理 pull_request 事件
    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": f"event type: {x_github_event}"}

    payload = await request.json()
    payload["delivery_id"] = x_github_delivery

    event = await adapter.parse_webhook_event(payload)
    if not event:
        return {"status": "ignored", "reason": "action not relevant"}

    # 交给编排器处理
    orchestrator = request.app.state.orchestrator
    task = await orchestrator.process_webhook_event(event)

    if task:
        return {"status": "accepted", "task_id": str(task.id)}
    return {"status": "ignored", "reason": "duplicate or no matching project"}


@router.post("/gitlab")
async def gitlab_webhook(
    request: Request,
    x_gitlab_token: str = Header(""),
    x_gitlab_event: str = Header(""),
):
    """GitLab Webhook 接收端点。"""
    config = request.app.state.config
    payload_bytes = await request.body()

    adapter = create_adapter(PlatformType.GITLAB, config)
    if not await adapter.verify_webhook_signature(payload_bytes, x_gitlab_token):
        raise HTTPException(status_code=401, detail="Invalid token")

    payload = await request.json()
    event = await adapter.parse_webhook_event(payload)
    if not event:
        return {"status": "ignored", "reason": "event not relevant"}

    orchestrator = request.app.state.orchestrator
    task = await orchestrator.process_webhook_event(event)

    if task:
        return {"status": "accepted", "task_id": str(task.id)}
    return {"status": "ignored", "reason": "duplicate or no matching project"}


@router.post("/gitee")
async def gitee_webhook(
    request: Request,
    x_gitee_token: str = Header(""),
    x_gitee_event: str = Header(""),
    x_gitee_timestamp: str = Header(""),
):
    """Gitee Webhook 接收端点。"""
    config = request.app.state.config
    payload_bytes = await request.body()

    adapter = create_adapter(PlatformType.GITEE, config)
    if not await adapter.verify_webhook_signature(
        payload_bytes, x_gitee_token, x_gitee_timestamp
    ):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    event = await adapter.parse_webhook_event(payload)
    if not event:
        return {"status": "ignored", "reason": "event not relevant"}

    orchestrator = request.app.state.orchestrator
    task = await orchestrator.process_webhook_event(event)

    if task:
        return {"status": "accepted", "task_id": str(task.id)}
    return {"status": "ignored", "reason": "duplicate or no matching project"}
