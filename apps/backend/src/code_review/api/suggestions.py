"""代码建议应用 API。"""

import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from code_review.models.db import ReviewComment, ReviewTask, CommentReply, Project

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/suggestions", tags=["suggestions"])


class ApplyResult(BaseModel):
    comment_id: str
    commit_sha: str
    applied_at: str


class BatchApplyRequest(BaseModel):
    comment_ids: list[str]


class BatchApplyResult(BaseModel):
    results: list[ApplyResult]
    failed: list[dict]


def _extract_code_block(suggestion: str) -> str:
    """从建议文本中提取代码块内容。"""
    matches = re.findall(r"```(?:\w+)?\n(.*?)```", suggestion, re.DOTALL)
    if matches:
        return matches[0]
    return suggestion


@router.post("/{comment_id}/apply")
async def apply_suggestion(comment_id: UUID, request: Request):
    session_factory = request.app.state.session_factory

    async with session_factory() as session:
        comment = await session.get(ReviewComment, comment_id)
        if not comment:
            raise HTTPException(status_code=404, detail="评论不存在")
        if not comment.suggestion:
            raise HTTPException(status_code=400, detail="该评论没有代码建议")
        if comment.applied:
            raise HTTPException(status_code=400, detail="该建议已被应用")

        task = await session.get(ReviewTask, comment.task_id)
        if not task:
            raise HTTPException(status_code=404, detail="评审任务不存在")

        project = await session.get(Project, task.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        orchestrator = request.app.state.orchestrator
        platform_config = await orchestrator._get_platform_config(project.platform)
        if not platform_config:
            raise HTTPException(status_code=500, detail="平台配置缺失")

        from code_review.adapters.factory import create_adapter
        adapter = create_adapter(
            platform=project.platform,
            platform_config=platform_config,
            project_webhook_secret=project.webhook_secret or "",
        )

        suggestion_content = _extract_code_block(comment.suggestion)

        try:
            commit_sha = await adapter.create_commit(
                project_id=project.platform_project_id,
                mr_iid=task.mr_iid,
                file_path=comment.file_path,
                content=suggestion_content,
                commit_message=f"fix: 应用 AI 评审建议 ({comment.file_path}:{comment.line_start})",
                branch=task.source_branch or "main",
            )
        except Exception as e:
            logger.error("应用建议失败: %s", e)
            raise HTTPException(status_code=500, detail=f"提交失败: {e}")

        comment.applied = True
        comment.applied_at = datetime.now(timezone.utc)
        comment.applied_commit_sha = commit_sha

        reply = CommentReply(
            comment_id=comment.id,
            author="system",
            content=f"建议已应用，commit: `{commit_sha[:8]}`",
            source="system",
        )
        session.add(reply)
        await session.commit()

        return ApplyResult(
            comment_id=str(comment.id),
            commit_sha=commit_sha,
            applied_at=comment.applied_at.isoformat(),
        )


@router.post("/batch-apply")
async def batch_apply(body: BatchApplyRequest, request: Request):
    results: list[ApplyResult] = []
    failed: list[dict] = []

    for cid in body.comment_ids:
        try:
            result = await apply_suggestion(UUID(cid), request)
            results.append(result)
        except Exception as e:
            failed.append({"comment_id": cid, "error": str(e)})

    return BatchApplyResult(results=results, failed=failed)
