"""评审任务 API 端点及系统健康检查。"""

import logging
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, func, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from code_review.models.db import ApiCallLog, Project, ReviewTask, ReviewComment, now_cst
from code_review.infrastructure.cache import event_dedup_cache
from code_review.adapters.factory import create_adapter
from code_review.api.logs import ApiCallLogResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["reviews"])


class ReviewTaskResponse(BaseModel):
    id: UUID
    project_id: UUID
    mr_iid: str
    mr_title: str | None
    mr_author: str | None
    mr_url: str | None
    source_branch: str | None
    target_branch: str | None
    status: str
    trigger_action: str | None
    model_name: str | None
    total_comments: int | None
    critical_count: int | None
    warning_count: int | None
    summary: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    parent_id: UUID | None = None
    revision: int = 1
    is_latest: bool = True
    latest_task_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class ReviewCommentResponse(BaseModel):
    id: UUID
    task_id: UUID
    file_path: str
    line_start: int
    line_end: int | None
    severity: str
    message: str
    suggestion: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeleteReviewsRequest(BaseModel):
    task_ids: list[UUID] = Field(..., min_length=1, max_length=100)


class BatchRetryRequest(BaseModel):
    task_ids: list[UUID] = Field(..., min_length=1, max_length=100)


class DeleteReviewsByDateRequest(BaseModel):
    start_date: datetime = Field(..., description="开始日期")
    end_date: datetime = Field(..., description="结束日期")
    project_id: UUID | None = None


class ManualReviewRequest(BaseModel):
    project_id: UUID = Field(..., description="项目 ID")
    mr_iid: str = Field(..., min_length=1, max_length=64, description="MR 短 ID")
    trigger_action: str = Field(default="manual", description="触发动作标识")


class NotifyResultResponse(BaseModel):
    sent: int
    failed: int
    channels: dict[str, bool]


# --------------- 辅助函数（消除重复代码） ---------------


def _escape_like(text: str) -> str:
    """转义 LIKE 通配符，防止 keyword 中的 % 和 _ 被当作通配符。"""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def _find_latest_child(session: AsyncSession, parent_id: UUID) -> ReviewTask | None:
    """查找主记录的最新子版本。"""
    stmt = (
        select(ReviewTask)
        .where(ReviewTask.parent_id == parent_id)
        .order_by(ReviewTask.revision.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _merge_parent_with_child(parent: ReviewTask, child: ReviewTask | None) -> ReviewTaskResponse:
    """将主记录元信息与子版本状态信息合并为响应。"""
    if child:
        return ReviewTaskResponse(
            id=parent.id,
            project_id=parent.project_id,
            mr_iid=parent.mr_iid,
            mr_title=parent.mr_title,
            mr_author=parent.mr_author,
            mr_url=parent.mr_url,
            source_branch=parent.source_branch,
            target_branch=parent.target_branch,
            status=child.status,
            trigger_action=child.trigger_action,
            model_name=child.model_name,
            total_comments=child.total_comments,
            critical_count=child.critical_count,
            warning_count=child.warning_count,
            summary=child.summary,
            error_message=child.error_message,
            started_at=child.started_at,
            completed_at=child.completed_at,
            created_at=parent.created_at,
            parent_id=None,
            revision=child.revision,
            is_latest=True,
            latest_task_id=child.id,
        )
    return ReviewTaskResponse(
        id=parent.id,
        project_id=parent.project_id,
        mr_iid=parent.mr_iid,
        mr_title=parent.mr_title,
        mr_author=parent.mr_author,
        mr_url=parent.mr_url,
        source_branch=parent.source_branch,
        target_branch=parent.target_branch,
        status=parent.status,
        trigger_action=parent.trigger_action,
        model_name=parent.model_name,
        total_comments=parent.total_comments,
        critical_count=parent.critical_count,
        warning_count=parent.warning_count,
        summary=parent.summary,
        error_message=parent.error_message,
        started_at=parent.started_at,
        completed_at=parent.completed_at,
        created_at=parent.created_at,
        parent_id=None,
        revision=parent.revision,
        is_latest=True,
        latest_task_id=None,
    )


async def _resolve_revision_task_id(
    session: AsyncSession, task: ReviewTask, revision: int | None = None,
) -> UUID:
    """根据 revision 参数解析实际要查询的 task_id。

    revision=1 时回退到主记录自身（主记录本身就是第 1 版）。
    无 revision 时返回最新子版本或主记录。
    """
    if task.parent_id is not None:
        return task.id

    if revision is not None:
        # revision=1 对应主记录自身
        if revision <= 1:
            return task.id
        rev_stmt = select(ReviewTask).where(
            ReviewTask.parent_id == task.id,
            ReviewTask.revision == revision,
        )
        rev_task = (await session.execute(rev_stmt)).scalar_one_or_none()
        return rev_task.id if rev_task else task.id

    latest = await _find_latest_child(session, task.id)
    return latest.id if latest else task.id


# --------------- API 端点 ---------------


@router.get("/reviews", response_model=list[ReviewTaskResponse])
async def list_reviews(
    request: Request,
    project_id: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    limit: int = 20,
    offset: int = 0,
):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        stmt = (
            select(ReviewTask)
            .where(ReviewTask.parent_id.is_(None))
            .order_by(ReviewTask.created_at.desc())
        )
        if project_id:
            stmt = stmt.where(ReviewTask.project_id == UUID(project_id))
        if status:
            stmt = stmt.where(ReviewTask.status == status)
        if keyword:
            stmt = stmt.where(ReviewTask.mr_title.ilike(f"%{_escape_like(keyword)}%", escape="\\"))
        stmt = stmt.offset(offset).limit(min(limit, 100))
        result = await session.execute(stmt)
        tasks = result.scalars().all()

        # 批量查询所有主记录的最新子版本（解决 N+1）
        parent_ids = [t.id for t in tasks]
        children_map: dict[UUID, ReviewTask] = {}
        if parent_ids:
            child_stmt = (
                select(ReviewTask)
                .where(ReviewTask.parent_id.in_(parent_ids))
                .order_by(ReviewTask.parent_id, ReviewTask.revision.desc())
            )
            child_rows = (await session.execute(child_stmt)).scalars().all()
            seen: set[UUID] = set()
            for child in child_rows:
                if child.parent_id and child.parent_id not in seen:
                    children_map[child.parent_id] = child
                    seen.add(child.parent_id)

        return [_merge_parent_with_child(t, children_map.get(t.id)) for t in tasks]


@router.get("/reviews/{task_id}", response_model=ReviewTaskResponse)
async def get_review(task_id: UUID, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        task = await session.get(ReviewTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Review task not found")

        if task.parent_id is None:
            latest = await _find_latest_child(session, task.id)
            return _merge_parent_with_child(task, latest)

        return task


@router.get("/reviews/{task_id}/comments", response_model=list[ReviewCommentResponse])
async def get_review_comments(task_id: UUID, request: Request, revision: int | None = None):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        task = await session.get(ReviewTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Review task not found")

        actual_task_id = await _resolve_revision_task_id(session, task, revision)

        stmt = (
            select(ReviewComment)
            .where(ReviewComment.task_id == actual_task_id)
            .order_by(ReviewComment.file_path, ReviewComment.line_start)
        )
        result = await session.execute(stmt)
        return result.scalars().all()


@router.get("/reviews/{task_id}/revisions", response_model=list[ReviewTaskResponse])
async def get_review_revisions(task_id: UUID, request: Request):
    """获取该 PR 下所有历史评审版本（含主记录本身）。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        task = await session.get(ReviewTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="评审记录不存在")

        parent_id = task.parent_id or task.id

        stmt = (
            select(ReviewTask)
            .where(
                (ReviewTask.id == parent_id) | (ReviewTask.parent_id == parent_id),
            )
            .order_by(ReviewTask.revision.asc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()


@router.delete("/reviews/all", status_code=204)
async def clear_all_reviews(request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        stmt = select(ReviewTask.event_id).where(ReviewTask.event_id.isnot(None))
        result = await session.execute(stmt)
        event_ids = [row[0] for row in result.all()]
        for event_id in event_ids:
            event_dedup_cache.delete(event_id)
        await session.execute(sql_delete(ReviewTask))
        await session.commit()
        event_dedup_cache.clear()
        logger.info(f"清空所有评审记录: {len(event_ids)} 条")


@router.delete("/reviews/{task_id}", status_code=204)
async def delete_review(task_id: UUID, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        task = await session.get(ReviewTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="评审记录不存在")
        if task.event_id:
            event_dedup_cache.delete(task.event_id)
        await session.delete(task)
        await session.commit()
        logger.info(f"删除评审记录: {task_id}")


@router.post("/reviews/batch-delete", status_code=204)
async def batch_delete_reviews(body: DeleteReviewsRequest, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        stmt = select(ReviewTask).where(ReviewTask.id.in_(body.task_ids))
        result = await session.execute(stmt)
        tasks = result.scalars().all()
        if not tasks:
            raise HTTPException(status_code=404, detail="未找到指定的评审记录")
        for task in tasks:
            if task.event_id:
                event_dedup_cache.delete(task.event_id)
        for task in tasks:
            await session.delete(task)
        await session.commit()
        logger.info(f"批量删除评审记录: {len(tasks)} 条")


@router.post("/reviews/batch-retry")
async def batch_retry_reviews(body: BatchRetryRequest, background_tasks: BackgroundTasks, request: Request):
    """批量重试失败的评审任务。

    对每个选中记录，找到其最新版本（子版本或自身），
    仅当最新版本状态为 failed 或 timeout 时才重试，跳过已完成的记录。
    """
    session_factory = request.app.state.session_factory
    orchestrator = request.app.state.orchestrator

    retried = 0
    skipped = 0

    for task_id in body.task_ids:
        async with session_factory() as session:
            task = await session.get(ReviewTask, task_id)
            if not task:
                continue

            # 找到实际要重试的目标：最新子版本或自身
            retry_target = task
            if task.parent_id is None:
                latest = await _find_latest_child(session, task.id)
                if latest:
                    retry_target = latest

            # 只重试最新版本为 failed 或 timeout 的记录
            if retry_target.status not in (ReviewTask.Status.FAILED, ReviewTask.Status.TIMEOUT):
                skipped += 1
                continue

            retry_target.status = ReviewTask.Status.PENDING
            retry_target.error_message = None
            retry_target.started_at = None
            retry_target.completed_at = None
            await session.commit()

        try:
            from code_review.infrastructure.celery_app import get_celery
            celery = get_celery()
            celery.send_task("code_review.execute_review", args=[str(retry_target.id)], queue="review")
        except Exception:
            background_tasks.add_task(orchestrator.execute_review, str(retry_target.id))
        retried += 1

    logger.info(f"批量重试评审记录: 重试 {retried} 条, 跳过 {skipped} 条")
    return {"retried": retried, "skipped": skipped, "total": len(body.task_ids)}


@router.post("/reviews/delete-by-date", status_code=204)
async def delete_reviews_by_date(body: DeleteReviewsByDateRequest, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        stmt = select(ReviewTask).where(
            ReviewTask.created_at >= body.start_date,
            ReviewTask.created_at <= body.end_date + timedelta(days=1),
        )
        if body.project_id:
            stmt = stmt.where(ReviewTask.project_id == body.project_id)
        result = await session.execute(stmt)
        tasks = result.scalars().all()
        if not tasks:
            raise HTTPException(status_code=404, detail="指定日期范围内没有评审记录")
        for task in tasks:
            if task.event_id:
                event_dedup_cache.delete(task.event_id)
        for task in tasks:
            await session.delete(task)
        await session.commit()
        logger.info(f"按日期删除评审记录: {len(tasks)} 条")


@router.post("/reviews/manual", response_model=ReviewTaskResponse, status_code=201)
async def create_manual_review(
    body: ManualReviewRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    session_factory = request.app.state.session_factory
    orchestrator = request.app.state.orchestrator

    async with session_factory() as session:
        project = await session.get(Project, body.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        if not project.enabled:
            raise HTTPException(status_code=400, detail="项目未启用")

        # 检查是否已存在该 PR 的主记录（FOR UPDATE 防止并发创建重复主记录）
        existing_parent = await session.execute(
            select(ReviewTask).where(
                ReviewTask.project_id == body.project_id,
                ReviewTask.mr_iid == body.mr_iid,
                ReviewTask.parent_id.is_(None),
            ).with_for_update()
        )
        parent_task = existing_parent.scalar_one_or_none()

        event_id = f"manual_{body.project_id}_{body.mr_iid}_{now_cst().strftime('%Y%m%d%H%M%S')}"

        platform_config = await orchestrator._get_platform_config(project.platform)
        if not platform_config:
            raise HTTPException(status_code=400, detail=f"未配置 {project.platform} 平台信息")

        adapter = create_adapter(
            platform=project.platform,
            platform_config=platform_config,
            project_webhook_secret=project.webhook_secret or "",
        )
        try:
            mr_info = await adapter.get_mr_info(project.platform_project_id, body.mr_iid)
        except Exception as e:
            logger.error(f"获取 MR 信息失败: {e}")
            raise HTTPException(status_code=400, detail=f"获取 MR 信息失败: {str(e)}")

        if parent_task:
            # 已有主记录，创建子版本（含主记录自身的 revision 防止重复）
            max_rev = (await session.execute(
                select(func.coalesce(func.max(ReviewTask.revision), 0))
                .where(
                    (ReviewTask.id == parent_task.id) | (ReviewTask.parent_id == parent_task.id)
                )
            )).scalar()
            task = ReviewTask(
                project_id=body.project_id,
                mr_iid=body.mr_iid,
                trigger_action=body.trigger_action,
                event_id=event_id,
                mr_title=mr_info.title,
                mr_author=mr_info.author,
                mr_url=mr_info.web_url or mr_info.url,
                source_branch=mr_info.source_branch,
                target_branch=mr_info.target_branch,
                status=ReviewTask.Status.PENDING,
                parent_id=parent_task.id,
                revision=max_rev + 1,
                is_latest=True,
            )
        else:
            task = ReviewTask(
                project_id=body.project_id,
                mr_iid=body.mr_iid,
                trigger_action=body.trigger_action,
                event_id=event_id,
                mr_title=mr_info.title,
                mr_author=mr_info.author,
                mr_url=mr_info.web_url or mr_info.url,
                source_branch=mr_info.source_branch,
                target_branch=mr_info.target_branch,
                status=ReviewTask.Status.PENDING,
                parent_id=None,
                revision=1,
                is_latest=True,
            )
        session.add(task)
        await session.commit()
        await session.refresh(task)

    async def run_review():
        try:
            await orchestrator.execute_review(str(task.id))
        except Exception as e:
            logger.error(f"手动评审失败: {e}")

    background_tasks.add_task(run_review)
    logger.info(f"创建手动评审任务: {task.id}")
    return task


@router.post("/reviews/{task_id}/retry", response_model=ReviewTaskResponse)
async def retry_review(task_id: UUID, background_tasks: BackgroundTasks, request: Request):
    """重试失败的评审任务。如果是主记录，则重试最新子版本。"""
    session_factory = request.app.state.session_factory
    orchestrator = request.app.state.orchestrator

    async with session_factory() as session:
        task = await session.get(ReviewTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="评审记录不存在")

        # 主记录 → 找最新子版本进行重试
        retry_task = task
        if task.parent_id is None:
            latest = await _find_latest_child(session, task.id)
            if latest:
                retry_task = latest

        if retry_task.status in (ReviewTask.Status.IN_PROGRESS, ReviewTask.Status.CANCELLED):
            detail = "评审任务正在执行中，无法重试" if retry_task.status == ReviewTask.Status.IN_PROGRESS else "已取消的任务不支持重试"
            raise HTTPException(status_code=409, detail=detail)

        retry_task.status = ReviewTask.Status.PENDING
        retry_task.error_message = None
        retry_task.started_at = None
        retry_task.completed_at = None
        await session.commit()
        await session.refresh(retry_task)

    actual_id = str(retry_task.id)
    from code_review.infrastructure.celery_app import get_celery
    try:
        celery = get_celery()
        celery_result = celery.send_task(
            "code_review.execute_review",
            args=[actual_id],
            queue="review",
        )
        async with session_factory() as session:
            db_task = await session.get(ReviewTask, retry_task.id)
            if db_task:
                db_task.celery_task_id = celery_result.id
                await session.commit()
    except Exception as e:
        logger.warning("Celery 分发失败，降级为同步执行: %s", e)
        background_tasks.add_task(orchestrator.execute_review, actual_id)

    async with session_factory() as session:
        refreshed = await session.get(ReviewTask, retry_task.id)
    logger.info("重试评审任务: %s", actual_id)
    return refreshed or retry_task


@router.post("/reviews/{task_id}/notify", response_model=NotifyResultResponse)
async def send_review_notification(task_id: UUID, request: Request):
    """对已完成的评审手动发送通知。"""
    session_factory = request.app.state.session_factory
    orchestrator = request.app.state.orchestrator

    async with session_factory() as session:
        task = await session.get(ReviewTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="评审记录不存在")
        if task.status != ReviewTask.Status.COMPLETED:
            raise HTTPException(status_code=400, detail="只能对已完成的评审发送通知")

        project = await session.get(Project, task.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        task_id_val = task.id
        project_id_val = task.project_id
        platform_val = project.platform
        mr_title = task.mr_title or ""
        mr_author = task.mr_author or ""
        mr_url = task.mr_url or ""
        project_name = project.name
        summary = task.summary or ""
        critical_count = task.critical_count or 0
        warning_count = task.warning_count or 0

    from code_review.core.notification import NotificationPayload
    from sqlalchemy import select as sql_select
    from code_review.models.db import ReviewComment as ReviewCommentDB

    async with session_factory() as session:
        result = await session.execute(
            sql_select(ReviewCommentDB).where(ReviewCommentDB.task_id == task_id_val)
        )
        comments = result.scalars().all()
        suggestion_count = sum(1 for c in comments if c.severity == "suggestion")
        info_count = sum(1 for c in comments if c.severity == "info")

    notification_payload = NotificationPayload(
        mr_title=mr_title,
        mr_author=mr_author,
        mr_url=mr_url,
        project_name=project_name,
        summary=summary,
        critical_count=critical_count,
        warning_count=warning_count,
        suggestion_count=suggestion_count,
        info_count=info_count,
        detail_link=mr_url,
    )

    from code_review.infrastructure.notification_manager import NotificationManager
    local_nm = NotificationManager(request.app.state.config)
    await local_nm.init_channels_from_db(
        session_factory,
        secret_key=orchestrator._secret_key,
        platform=platform_val,
    )
    channels = await local_nm.notify_all(
        notification_payload,
        project_id=project_id_val,
        task_id=task_id_val,
        session_factory=session_factory,
    )

    sent = sum(1 for v in channels.values() if v)
    failed = sum(1 for v in channels.values() if not v)
    logger.info("手动发送通知: task=%s, sent=%d, failed=%d", task_id, sent, failed)
    return NotifyResultResponse(sent=sent, failed=failed, channels=channels)


@router.get("/reviews/{task_id}/logs", response_model=list[ApiCallLogResponse])
async def get_review_logs(task_id: UUID, request: Request, revision: int | None = None):
    """查询评审任务的 API 调用日志。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        task = await session.get(ReviewTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="评审记录不存在")

        actual_task_id = await _resolve_revision_task_id(session, task, revision)

        stmt = (
            select(ApiCallLog)
            .where(ApiCallLog.task_id == actual_task_id)
            .order_by(ApiCallLog.created_at.asc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()


@router.post("/reviews/check-timeout")
async def check_review_timeouts(request: Request):
    """检查并标记超时的评审任务。

    根据 review_timeout_seconds 配置，将 in_progress 状态超过阈值的任务标记为 timeout。
    """
    session_factory = request.app.state.session_factory
    config = request.app.state.config
    timeout_seconds = config.review.review_timeout_seconds

    async with session_factory() as session:
        # 数据库列为 timestamp without time zone，使用 naive datetime 比较
        now = now_cst().replace(tzinfo=None)
        cutoff = now - timedelta(seconds=timeout_seconds)

        stmt = select(ReviewTask).where(
            ReviewTask.status == ReviewTask.Status.IN_PROGRESS,
            ReviewTask.started_at.isnot(None),
            ReviewTask.started_at < cutoff,
        )
        result = await session.execute(stmt)
        timed_out = result.scalars().all()

        count = 0
        for task in timed_out:
            task.status = ReviewTask.Status.TIMEOUT
            task.error_message = f"评审超时（超过 {timeout_seconds} 秒）"
            task.completed_at = now
            count += 1
            logger.info("评审任务超时: %s, started_at=%s", task.id, task.started_at)

        if count:
            await session.commit()

    return {"checked": True, "timed_out": count, "timeout_seconds": timeout_seconds}


@router.get("/health")
async def health_check(request: Request):
    checks = {"database": False}
    try:
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            await session.execute(select(func.count()).select_from(Project))
            checks["database"] = True
    except Exception as e:
        logger.error("Database health check failed: %s", e)

    notification_manager = request.app.state.notification_manager
    checks["notifications"] = await notification_manager.health_check()

    all_healthy = all(
        v if isinstance(v, bool) else all(v.values())
        for v in checks.values()
    )
    return {"status": "healthy" if all_healthy else "degraded", "checks": checks}
