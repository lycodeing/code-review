"""项目管理 API 端点。"""

from datetime import datetime, timezone
from uuid import UUID

from code_review.models.db import now_cst

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select

from code_review.models.db import Project

router = APIRouter(prefix="/api/v1", tags=["projects"])


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


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(body: ProjectCreate, request: Request):
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
    enabled: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    limit: int | None = Query(default=None),
    offset: int | None = Query(default=None),
):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        stmt = select(Project).order_by(Project.created_at.desc())
        if enabled is not None and enabled != "":
            try:
                stmt = stmt.where(Project.enabled == int(enabled))
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
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        project = await session.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return project


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: UUID, body: ProjectUpdate, request: Request):
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
        project.updated_at = now_cst()
        await session.commit()
        await session.refresh(project)
        return project


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: UUID, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        project = await session.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        await session.delete(project)
        await session.commit()


class BatchProjectAction(BaseModel):
    project_ids: list[UUID] = Field(..., min_length=1, max_length=100)
    action: str = Field(..., pattern=r"^(enable|disable|delete)$")


@router.post("/projects/batch")
async def batch_project_action(body: BatchProjectAction, request: Request):
    """批量启用/禁用/删除项目。"""
    session_factory = request.app.state.session_factory
    affected = 0

    async with session_factory() as session:
        stmt = select(Project).where(Project.id.in_(body.project_ids))
        result = await session.execute(stmt)
        projects = result.scalars().all()

        for project in projects:
            match body.action:
                case "enable":
                    project.enabled = 1
                case "disable":
                    project.enabled = 0
                case "delete":
                    await session.delete(project)
            affected += 1

        await session.commit()

    return {"action": body.action, "affected": affected}
