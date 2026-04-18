"""评审任务 API 端点及系统健康检查。"""

import logging
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, func, delete as sql_delete

from code_review.models.db import Project, ReviewTask, ReviewComment
from code_review.infrastructure.cache import event_dedup_cache
from code_review.adapters.factory import create_adapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["reviews"])


class ReviewTaskResponse(BaseModel):
    id: UUID
    project_id: UUID
    mr_iid: str
    mr_title: str | None
    mr_author: str | None
    mr_url: str | None
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


class DeleteReviewsByDateRequest(BaseModel):
    start_date: datetime = Field(..., description="开始日期")
    end_date: datetime = Field(..., description="结束日期")
    project_id: UUID | None = None


class ManualReviewRequest(BaseModel):
    project_id: UUID = Field(..., description="项目 ID")
    mr_iid: str = Field(..., min_length=1, max_length=64, description="MR 短 ID")
    trigger_action: str = Field(default="manual", description="触发动作标识")


@router.get("/reviews", response_model=list[ReviewTaskResponse])
async def list_reviews(
    request: Request,
    project_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        stmt = select(ReviewTask).order_by(ReviewTask.created_at.desc())
        if project_id:
            stmt = stmt.where(ReviewTask.project_id == UUID(project_id))
        if status:
            stmt = stmt.where(ReviewTask.status == status)
        stmt = stmt.offset(offset).limit(min(limit, 100))
        result = await session.execute(stmt)
        return result.scalars().all()


@router.get("/reviews/{task_id}", response_model=ReviewTaskResponse)
async def get_review(task_id: UUID, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        task = await session.get(ReviewTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Review task not found")
        return task


@router.get("/reviews/{task_id}/comments", response_model=list[ReviewCommentResponse])
async def get_review_comments(task_id: UUID, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        stmt = (
            select(ReviewComment)
            .where(ReviewComment.task_id == task_id)
            .order_by(ReviewComment.file_path, ReviewComment.line_start)
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

        event_id = f"manual_{body.project_id}_{body.mr_iid}"
        stmt = select(ReviewTask).where(
            ReviewTask.project_id == body.project_id,
            ReviewTask.mr_iid == body.mr_iid,
            ReviewTask.event_id == event_id,
        )
        if (await session.execute(stmt)).scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail="该 MR 已存在评审记录，请先删除原有记录后再手动触发",
            )

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
