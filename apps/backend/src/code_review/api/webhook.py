"""Webhook 接收端点。"""

import logging

from fastapi import APIRouter, Request, HTTPException, Header

from code_review.adapters.github_adapter import GitHubAdapter
from code_review.adapters.gitlab_adapter import GitLabAdapter
from code_review.adapters.gitee_adapter import GiteeAdapter
from code_review.infrastructure.cache import event_dedup_cache

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
    adapter = GitHubAdapter(
        token=config.github.token or "",
        api_url=config.github.api_url or "https://api.github.com",
    )
    adapter.set_webhook_secret(config.github.webhook_secret or "")
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

    # 去重检查
    if event_dedup_cache.exists(event.event_id):
        logger.info("Duplicate event ignored: %s", event.event_id)
        return {"status": "ignored", "reason": "重复请求"}

    # 交给编排器处理
    orchestrator = request.app.state.orchestrator
    task = await orchestrator.process_webhook_event(event)

    if task:
        return {"status": "accepted", "task_id": str(task.id)}
    return {"status": "ignored", "reason": "no matching project"}


@router.post("/gitlab")
async def gitlab_webhook(
    request: Request,
    x_gitlab_token: str = Header(""),
    x_gitlab_event: str = Header(""),
):
    """GitLab Webhook 接收端点。"""
    config = request.app.state.config
    payload_bytes = await request.body()

    adapter = GitLabAdapter(
        token=config.gitlab.token or "",
        api_url=config.gitlab.api_url or "https://gitlab.com/api/v4",
    )
    adapter.set_webhook_secret(config.gitlab.webhook_secret or "")
    if not await adapter.verify_webhook_signature(payload_bytes, x_gitlab_token):
        raise HTTPException(status_code=401, detail="Invalid token")

    payload = await request.json()
    event = await adapter.parse_webhook_event(payload)
    if not event:
        return {"status": "ignored", "reason": "event not relevant"}

    # 去重检查
    if event_dedup_cache.exists(event.event_id):
        logger.info("Duplicate event ignored: %s", event.event_id)
        return {"status": "ignored", "reason": "重复请求"}

    orchestrator = request.app.state.orchestrator
    task = await orchestrator.process_webhook_event(event)

    if task:
        return {"status": "accepted", "task_id": str(task.id)}
    return {"status": "ignored", "reason": "no matching project"}


@router.post("/gitee")
async def gitee_webhook(
    request: Request,
    x_gitee_token: str = Header(""),
    x_gitee_event: str = Header(""),
    x_gitee_timestamp: str = Header(""),
    x_gitee_ping: str = Header(""),
):
    """Gitee Webhook 接收端点。"""
    config = request.app.state.config
    payload_bytes = await request.body()

    # Ping 测试直接返回成功
    if x_gitee_ping == "true":
        return {"status": "ok", "message": "pong"}

    # 创建 Gitee 适配器（使用环境变量配置）
    adapter = GiteeAdapter(
        token=config.gitee.token or "",
        api_url=config.gitee.api_url or "https://gitee.com/api/v5",
    )
    adapter.set_webhook_secret(config.gitee.webhook_secret or "")

    # 验证签名
    if not await adapter.verify_webhook_signature(
        payload_bytes, x_gitee_token, x_gitee_timestamp
    ):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()

    # Gitee 事件类型可能是 "Pull Request"、"Merge Request Hook" 或 "Push Hook" 等
    # 仅处理 Merge Request 事件，忽略 Push 等其他事件
    event_type = (x_gitee_event or "").lower()
    # 检查是否包含 merge 或 pull 关键字
    if "merge" in event_type or "pull" in event_type:
        event = await adapter.parse_webhook_event(payload)
        if not event:
            return {"status": "ignored", "reason": "action not relevant"}

        # 去重检查
        if event_dedup_cache.exists(event.event_id):
            logger.info("Duplicate event ignored: %s", event.event_id)
            return {"status": "ignored", "reason": "重复请求"}

        logger.debug("Gitee webhook event: project=%s, mr_iid=%s, action=%s", event.project_id, event.mr_iid, event.action)

        orchestrator = request.app.state.orchestrator
        task = await orchestrator.process_webhook_event(event)

        if task:
            return {"status": "accepted", "task_id": str(task.id)}
        return {"status": "ignored", "reason": "no matching project"}

    # 其他事件类型（如 Push Hook）暂不处理
    return {"status": "ignored", "reason": f"event type not supported: {x_gitee_event}"}
