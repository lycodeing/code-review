"""Webhook 接收端点。"""

import logging

from fastapi import APIRouter, Request, HTTPException, Header

from code_review.adapters.github_adapter import GitHubAdapter
from code_review.adapters.gitlab_adapter import GitLabAdapter
from code_review.adapters.gitee_adapter import GiteeAdapter
from code_review.core.platform import PlatformType, WebhookEvent
from code_review.infrastructure.cache import event_dedup_cache
from code_review.services.command_router import CommandRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])

# 命令路由器实例
_command_router = CommandRouter()


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

    payload = await request.json()
    payload["delivery_id"] = x_github_delivery

    # 处理 PR 评论命令（issue_comment 事件）
    if x_github_event == "issue_comment" and payload.get("action") == "created":
        return await _handle_github_comment_command(request, payload, adapter)

    # 仅处理 pull_request 事件
    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": f"event type: {x_github_event}"}

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

    # 处理 MR 评论命令（note 事件）
    object_kind = payload.get("object_kind")
    if object_kind == "note" and payload.get("object_attributes", {}).get("action") == "create":
        return await _handle_gitlab_comment_command(request, payload)

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
    event_type = (x_gitee_event or "").lower()

    # 处理 PR 评论命令
    if "comment" in event_type or "note" in event_type:
        return await _handle_gitee_comment_command(request, payload)

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


async def _handle_github_comment_command(
    request: Request,
    payload: dict,
    adapter: GitHubAdapter,
):
    """处理 GitHub PR 评论命令。

    支持的命令：
    - /review: 触发完整评审
    - /describe: 生成 PR 描述
    - /improve: 使用改进模板触发评审
    - /analyze: 仅执行规则引擎检查
    """
    comment = payload.get("comment", {})
    comment_body = comment.get("body", "")
    issue = payload.get("issue", {})

    # 检查是否为 PR 评论（issue 包含 pull_request 字段）
    if "pull_request" not in issue:
        return {"status": "ignored", "reason": "不是 PR 评论"}

    # 过滤 bot 用户（防止循环）
    sender = payload.get("sender", {})
    sender_login = sender.get("login", "")
    if sender_login.endswith("[bot]"):
        logger.info("忽略 bot 用户评论: %s", sender_login)
        return {"status": "ignored", "reason": "bot 用户评论"}

    # 解析命令
    parsed = _command_router.parse_command(comment_body)
    if not parsed:
        return {"status": "ignored", "reason": "不是命令"}

    command_name, args = parsed
    logger.info("检测到 GitHub 评论命令: %s, 用户: %s", command_name, sender_login)

    # 构建 WebhookEvent
    pr = issue.get("pull_request", {})
    repo = payload.get("repository", {})

    event = WebhookEvent(
        platform=PlatformType.GITHUB,
        project_id=repo.get("full_name", ""),
        mr_id=str(pr.get("id", "")),
        mr_iid=str(issue.get("number", "")),
        action="command",
        event_id=payload.get("delivery_id", f"comment-{comment.get('id', '')}"),
        mr_title=pr.get("title"),
        mr_author=pr.get("user", {}).get("login"),
        mr_url=pr.get("html_url", ""),
        source_branch=pr.get("head", {}).get("ref"),
        target_branch=pr.get("base", {}).get("ref"),
        raw_payload={
            "command": command_name,
            "args": args,
            "comment_id": str(comment.get("id", "")),
            "sender_login": sender_login,
            "project_id": repo.get("full_name", ""),
            "mr_iid": str(issue.get("number", "")),
        },
    )

    # 去重检查
    if event_dedup_cache.exists(event.event_id):
        logger.info("Duplicate command ignored: %s", event.event_id)
        return {"status": "ignored", "reason": "重复命令"}

    # 交给编排器处理
    orchestrator = request.app.state.orchestrator
    task = await orchestrator.process_webhook_event(event)

    if task:
        return {"status": "accepted", "task_id": str(task.id)}
    return {"status": "ignored", "reason": "命令处理失败"}


async def _handle_gitlab_comment_command(
    request: Request,
    payload: dict,
):
    """处理 GitLab MR 评论命令。

    支持的命令：
    - /review: 触发完整评审
    - /describe: 生成 MR 描述
    - /improve: 使用改进模板触发评审
    - /analyze: 仅执行规则引擎检查
    """
    # GitLab Merge Request comment 事件
    object_kind = payload.get("object_kind")
    if object_kind != "note":
        return {"status": "ignored", "reason": f"事件类型: {object_kind}"}

    # 检查是否为 MR 评论（note 包含 merge_request 字段）
    mr_attrs = payload.get("merge_request", {})
    if not mr_attrs:
        return {"status": "ignored", "reason": "不是 MR 评论"}

    comment_body = payload.get("object_attributes", {}).get("note", "")
    user = payload.get("user", {})
    username = user.get("username", "")

    # 过滤 bot 用户
    if username.endswith("[bot]") or username == "gitlab":
        logger.info("忽略 bot 用户评论: %s", username)
        return {"status": "ignored", "reason": "bot 用户评论"}

    # 解析命令
    parsed = _command_router.parse_command(comment_body)
    if not parsed:
        return {"status": "ignored", "reason": "不是命令"}

    command_name, args = parsed
    logger.info("检测到 GitLab 评论命令: %s, 用户: %s", command_name, username)

    # 构建 WebhookEvent
    project = payload.get("project", {})
    event = WebhookEvent(
        platform=PlatformType.GITLAB,
        project_id=str(project.get("id", "")),
        mr_id=str(mr_attrs.get("id", "")),
        mr_iid=str(mr_attrs.get("iid", "")),
        action="command",
        event_id=f"note-{payload.get('object_attributes', {}).get('id', '')}",
        mr_title=mr_attrs.get("title"),
        mr_author=mr_attrs.get("author", {}).get("username"),
        mr_url=mr_attrs.get("url"),
        source_branch=mr_attrs.get("source_branch"),
        target_branch=mr_attrs.get("target_branch"),
        raw_payload={
            "command": command_name,
            "args": args,
            "comment_id": str(payload.get("object_attributes", {}).get("id", "")),
            "sender_login": username,
            "project_id": str(project.get("id", "")),
            "mr_iid": str(mr_attrs.get("iid", "")),
        },
    )

    # 去重检查
    if event_dedup_cache.exists(event.event_id):
        logger.info("Duplicate command ignored: %s", event.event_id)
        return {"status": "ignored", "reason": "重复命令"}

    # 交给编排器处理
    orchestrator = request.app.state.orchestrator
    task = await orchestrator.process_webhook_event(event)

    if task:
        return {"status": "accepted", "task_id": str(task.id)}
    return {"status": "ignored", "reason": "命令处理失败"}


async def _handle_gitee_comment_command(
    request: Request,
    payload: dict,
):
    """处理 Gitee PR 评论命令。

    支持的命令：
    - /review: 触发完整评审
    - /describe: 生成 PR 描述
    - /improve: 使用改进模板触发评审
    - /analyze: 仅执行规则引擎检查
    """
    # Gitee Pull Request comment 事件
    action = payload.get("action", "")
    if action != "comment":
        return {"status": "ignored", "reason": f"动作类型: {action}"}

    comment_body = payload.get("comment", {}).get("body", "")
    sender = payload.get("sender", {})
    sender_login = sender.get("login", "")

    # 过滤 bot 用户
    if sender_login.endswith("[bot]"):
        logger.info("忽略 bot 用户评论: %s", sender_login)
        return {"status": "ignored", "reason": "bot 用户评论"}

    # 解析命令
    parsed = _command_router.parse_command(comment_body)
    if not parsed:
        return {"status": "ignored", "reason": "不是命令"}

    command_name, args = parsed
    logger.info("检测到 Gitee 评论命令: %s, 用户: %s", command_name, sender_login)

    # 构建 WebhookEvent
    pr = payload.get("pull_request", {})
    project = payload.get("repository", {})

    event = WebhookEvent(
        platform=PlatformType.GITEE,
        project_id=str(project.get("id", "")),
        mr_id=str(pr.get("id", "")),
        mr_iid=str(pr.get("number", "")),
        action="command",
        event_id=f"comment-{payload.get('comment', {}).get('id', '')}",
        mr_title=pr.get("title"),
        mr_author=pr.get("user", {}).get("login"),
        mr_url=pr.get("html_url", ""),
        source_branch=pr.get("head", {}).get("ref"),
        target_branch=pr.get("base", {}).get("ref"),
        raw_payload={
            "command": command_name,
            "args": args,
            "comment_id": str(payload.get("comment", {}).get("id", "")),
            "sender_login": sender_login,
            "project_id": str(project.get("id", "")),
            "mr_iid": str(pr.get("number", "")),
        },
    )

    # 去重检查
    if event_dedup_cache.exists(event.event_id):
        logger.info("Duplicate command ignored: %s", event.event_id)
        return {"status": "ignored", "reason": "重复命令"}

    # 交给编排器处理
    orchestrator = request.app.state.orchestrator
    task = await orchestrator.process_webhook_event(event)

    if task:
        return {"status": "accepted", "task_id": str(task.id)}
    return {"status": "ignored", "reason": "命令处理失败"}
