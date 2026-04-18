"""管理 API 端点 — 项目管理、评审历史查询、健康检查。"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Query, BackgroundTasks
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import select, func, desc, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from code_review.models.db import Project, ReviewTask, ReviewComment
from code_review.infrastructure.cache import event_dedup_cache
from code_review.adapters.factory import create_adapter
from code_review.core.platform import PlatformType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["management"])


# ---- 请求/响应模型 ----

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    platform: str = Field(..., pattern=r"^(github|gitlab|gitee)$")
    platform_project_id: str = Field(..., min_length=1)
    webhook_secret: str = ""
    config: dict | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    webhook_secret: str | None = None
    config: dict | None = None
    enabled: int | None = Field(None, ge=0, le=1)


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    platform: str
    platform_project_id: str
    enabled: int
    config: dict | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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

    model_config = {"from_attributes": True}


# ---- 项目管理 ----

@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(body: ProjectCreate, request: Request):
    """创建项目。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        project = Project(
            name=body.name,
            platform=body.platform,
            platform_project_id=body.platform_project_id,
            webhook_secret=body.webhook_secret,
            config=body.config,
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)
        return project


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    request: Request,
    enabled: str | None = Query(default=None, description="启用状态（0/1）"),
    keyword: str | None = Query(default=None, description="关键词搜索（项目名称）"),
    platform: str | None = Query(default=None, description="平台过滤（github/gitlab/gitee）"),
    limit: int | None = Query(default=None, description="返回数量限制"),
    offset: int | None = Query(default=None, description="偏移量（用于分页）"),
):
    """列出所有项目。

    支持的查询参数：
    - enabled: 启用状态（0/1）
    - keyword: 关键词搜索（项目名称）
    - platform: 平台过滤（github/gitlab/gitee）
    - limit: 返回数量限制
    - offset: 偏移量（用于分页）
    """
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        stmt = select(Project).order_by(Project.created_at.desc())

        # 处理 enabled 参数（空字符串视为 None）
        if enabled is not None and enabled != "":
            try:
                enabled_int = int(enabled)
                stmt = stmt.where(Project.enabled == enabled_int)
            except ValueError:
                pass

        if keyword:
            stmt = stmt.where(Project.name.ilike(f"%{keyword}%"))
        if platform:
            stmt = stmt.where(Project.platform == platform)
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)

        result = await session.execute(stmt)
        return result.scalars().all()


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: UUID, request: Request):
    """获取项目详情。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        project = await session.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return project


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: UUID, body: ProjectUpdate, request: Request):
    """更新项目配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        project = await session.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        if body.name is not None:
            project.name = body.name
        if body.webhook_secret is not None:
            project.webhook_secret = body.webhook_secret
        if body.config is not None:
            project.config = body.config
        if body.enabled is not None:
            project.enabled = body.enabled
        project.updated_at = datetime.now(tz=timezone.utc)

        await session.commit()
        await session.refresh(project)
        return project


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: UUID, request: Request):
    """删除项目。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        project = await session.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        await session.delete(project)
        await session.commit()


# ---- 评审历史 ----

@router.get("/reviews", response_model=list[ReviewTaskResponse])
async def list_reviews(
    request: Request,
    project_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
):
    """查询评审任务列表。"""
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
    """获取评审任务详情。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        task = await session.get(ReviewTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Review task not found")
        return task


@router.get("/reviews/{task_id}/comments", response_model=list[ReviewCommentResponse])
async def get_review_comments(task_id: UUID, request: Request):
    """获取评审任务的所有评论。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        stmt = (
            select(ReviewComment)
            .where(ReviewComment.task_id == task_id)
            .order_by(ReviewComment.file_path, ReviewComment.line_start)
        )
        result = await session.execute(stmt)
        return result.scalars().all()


# ---- 评审记录管理 ----

class DeleteReviewsRequest(BaseModel):
    """批量删除评审记录请求。"""
    task_ids: list[UUID] = Field(..., min_length=1, max_length=100)


class DeleteReviewsByDateRequest(BaseModel):
    """按日期范围删除评审记录请求。"""
    start_date: datetime = Field(..., description="开始日期")
    end_date: datetime = Field(..., description="结束日期")
    project_id: UUID | None = None


class ManualReviewRequest(BaseModel):
    """手动触发评审请求。"""
    project_id: UUID = Field(..., description="项目 ID")
    mr_iid: str = Field(..., min_length=1, max_length=64, description="MR 短 ID")
    trigger_action: str = Field(default="manual", description="触发动作标识")


@router.delete("/reviews/all", status_code=204)
async def clear_all_reviews(request: Request):
    """清空所有评审记录（包括评论和去重缓存）。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        # 先获取所有任务的 event_id（用于清理缓存）
        stmt = select(ReviewTask.event_id).where(ReviewTask.event_id.isnot(None))
        result = await session.execute(stmt)
        event_ids = [row[0] for row in result.all()]

        # 清空去重缓存
        for event_id in event_ids:
            event_dedup_cache.delete(event_id)

        # 删除所有任务（级联删除评论）
        await session.execute(sql_delete(ReviewTask))
        await session.commit()

        # 清空进程内缓存的所有数据
        event_dedup_cache.clear()

        logger.info(f"清空所有评审记录: {len(event_ids)} 条，清理缓存: {len(event_ids)} 个")


@router.delete("/reviews/{task_id}", status_code=204)
async def delete_review(task_id: UUID, request: Request):
    """删除单条评审记录。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        task = await session.get(ReviewTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="评审记录不存在")

        # 清理去重缓存
        if task.event_id:
            event_dedup_cache.delete(task.event_id)
            logger.info(f"清理去重缓存: {task.event_id}")

        await session.delete(task)
        await session.commit()
        logger.info(f"删除评审记录: {task_id}")


@router.post("/reviews/batch-delete", status_code=204)
async def batch_delete_reviews(body: DeleteReviewsRequest, request: Request):
    """批量删除评审记录。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        # 查询要删除的任务
        stmt = select(ReviewTask).where(ReviewTask.id.in_(body.task_ids))
        result = await session.execute(stmt)
        tasks = result.scalars().all()

        if not tasks:
            raise HTTPException(status_code=404, detail="未找到指定的评审记录")

        # 清理去重缓存
        for task in tasks:
            if task.event_id:
                event_dedup_cache.delete(task.event_id)

        # 删除任务（级联删除评论）
        for task in tasks:
            await session.delete(task)

        await session.commit()
        logger.info(f"批量删除评审记录: {len(tasks)} 条，清理缓存: {sum(1 for t in tasks if t.event_id)} 个")


@router.post("/reviews/delete-by-date", status_code=204)
async def delete_reviews_by_date(body: DeleteReviewsByDateRequest, request: Request):
    """按日期范围删除评审记录。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        # 构建查询条件
        stmt = select(ReviewTask).where(
            ReviewTask.created_at >= body.start_date,
            ReviewTask.created_at <= body.end_date + timedelta(days=1),  # 包含结束日期当天
        )
        if body.project_id:
            stmt = stmt.where(ReviewTask.project_id == body.project_id)

        # 查询要删除的任务
        result = await session.execute(stmt)
        tasks = result.scalars().all()

        if not tasks:
            raise HTTPException(status_code=404, detail="指定日期范围内没有评审记录")

        # 清理去重缓存
        for task in tasks:
            if task.event_id:
                event_dedup_cache.delete(task.event_id)

        # 删除任务
        for task in tasks:
            await session.delete(task)

        await session.commit()
        logger.info(
            f"按日期删除评审记录: {len(tasks)} 条 ({body.start_date} 至 {body.end_date})，"
            f"清理缓存: {sum(1 for t in tasks if t.event_id)} 个"
        )


@router.post("/reviews/manual", response_model=ReviewTaskResponse, status_code=201)
async def create_manual_review(body: ManualReviewRequest, background_tasks: BackgroundTasks, request: Request):
    """手动触发代码评审。"""
    session_factory = request.app.state.session_factory
    orchestrator = request.app.state.orchestrator

    async with session_factory() as session:
        # 验证项目存在
        project = await session.get(Project, body.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        if not project.enabled:
            raise HTTPException(status_code=400, detail="项目未启用")

        # 检查是否已存在相同的事件
        event_id = f"manual_{body.project_id}_{body.mr_iid}"
        stmt = select(ReviewTask).where(
            ReviewTask.project_id == body.project_id,
            ReviewTask.mr_iid == body.mr_iid,
            ReviewTask.event_id == event_id
        )
        existing = await session.execute(stmt)
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail="该 MR 已存在评审记录，请先删除原有记录后再手动触发"
            )

        # 获取平台配置
        platform_config = await orchestrator._get_platform_config(project.platform)
        if not platform_config:
            raise HTTPException(status_code=400, detail=f"未配置 {project.platform} 平台信息")

        # 创建适配器并获取 MR 信息
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

        # 创建评审任务（填充基本信息）
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

    # 使用后台任务异步执行评审
    async def run_review():
        try:
            await orchestrator.execute_review(str(task.id))
        except Exception as e:
            logger.error(f"手动评审失败: {e}")

    background_tasks.add_task(run_review)

    logger.info(f"创建手动评审任务: {task.id} (项目: {project.name}, MR: {mr_info.title})")
    return task


# ---- 健康检查 ----

@router.get("/health")
async def health_check(request: Request):
    """系统健康检查。"""
    config = request.app.state.config
    checks = {"database": False}

    try:
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            await session.execute(select(func.count()).select_from(Project))
            checks["database"] = True
    except Exception as e:
        logger.error("Database health check failed: %s", e)

    # 通知渠道检查
    notification_manager = request.app.state.notification_manager
    checks["notifications"] = await notification_manager.health_check()

    all_healthy = all(
        v if isinstance(v, bool) else all(v.values())
        for v in checks.values()
    )

    return {"status": "healthy" if all_healthy else "degraded", "checks": checks}
