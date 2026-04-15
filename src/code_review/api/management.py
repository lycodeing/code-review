"""管理 API 端点 — 项目管理、评审历史查询、健康检查。"""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from code_review.models.db import Project, ReviewTask, ReviewComment

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
    id: str
    name: str
    platform: str
    platform_project_id: str
    enabled: int
    config: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewTaskResponse(BaseModel):
    id: str
    project_id: str
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

    model_config = {"from_attributes": True}


class ReviewCommentResponse(BaseModel):
    id: str
    task_id: str
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
async def list_projects(request: Request, enabled: int | None = None):
    """列出所有项目。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        stmt = select(Project).order_by(Project.created_at.desc())
        if enabled is not None:
            stmt = stmt.where(Project.enabled == enabled)
        result = await session.execute(stmt)
        return result.scalars().all()


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, request: Request):
    """获取项目详情。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        project = await session.get(Project, UUID(project_id))
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return project


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, body: ProjectUpdate, request: Request):
    """更新项目配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        project = await session.get(Project, UUID(project_id))
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
        project.updated_at = datetime.utcnow()

        await session.commit()
        await session.refresh(project)
        return project


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: str, request: Request):
    """删除项目。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        project = await session.get(Project, UUID(project_id))
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
async def get_review(task_id: str, request: Request):
    """获取评审任务详情。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        task = await session.get(ReviewTask, UUID(task_id))
        if not task:
            raise HTTPException(status_code=404, detail="Review task not found")
        return task


@router.get("/reviews/{task_id}/comments", response_model=list[ReviewCommentResponse])
async def get_review_comments(task_id: str, request: Request):
    """获取评审任务的所有评论。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        stmt = (
            select(ReviewComment)
            .where(ReviewComment.task_id == UUID(task_id))
            .order_by(ReviewComment.file_path, ReviewComment.line_start)
        )
        result = await session.execute(stmt)
        return result.scalars().all()


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
