"""Prompt 模板 CRUD API 端点。"""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from code_review.models.db import PromptTemplate
from code_review.services.prompt_template_service import PromptTemplateService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/prompt-templates", tags=["prompt-templates"])

# 项目绑定路由
binding_router = APIRouter(prefix="/api/v1/projects/{project_id}/prompt-bindings", tags=["prompt-bindings"])


# ---- 请求/响应模型 ----

class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    category: str = Field(default="default", max_length=64)
    locale: str = Field(default="zh", max_length=10)


class TemplateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    content: str | None = Field(None, min_length=1)
    category: str | None = Field(None, max_length=64)
    locale: str | None = Field(None, max_length=10)
    enabled: int | None = Field(None, ge=0, le=1)


class TemplateResponse(BaseModel):
    id: UUID
    name: str
    content: str
    category: str
    locale: str
    enabled: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateListResponse(BaseModel):
    items: list[TemplateResponse]
    total: int


class PromptBindingCreate(BaseModel):
    """创建项目-模板绑定请求。"""
    template_id: UUID
    is_default: bool = Field(default=False, description="是否设为默认")
    priority: int = Field(default=0, ge=0, le=100, description="优先级（0-100）")


class PromptBindingUpdate(BaseModel):
    """更新绑定请求。"""
    is_default: bool | None = None
    priority: int | None = Field(None, ge=0, le=100)
    enabled: bool | None = None


class PromptBindingResponse(BaseModel):
    """绑定响应。"""
    id: UUID
    project_id: UUID
    template_id: UUID
    template: TemplateResponse | None = None
    is_default: bool
    priority: int
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---- 模板 CRUD 端点 ----

@router.post("", response_model=TemplateResponse, status_code=201)
async def create_template(body: TemplateCreate, request: Request):
    """创建 Prompt 模板。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = PromptTemplateService(session)
        # 检查名称唯一性
        existing = await svc.get_by_name(body.name)
        if existing:
            raise HTTPException(status_code=409, detail=f"Template '{body.name}' already exists")
        tpl = await svc.create(
            name=body.name,
            content=body.content,
            category=body.category,
            locale=body.locale,
        )
        return tpl


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    request: Request,
    category: str | None = None,
    locale: str | None = None,
    enabled: int | None = None,
    offset: int = 0,
    limit: int = 50,
):
    """查询模板列表，支持按分类、语言、启用状态筛选。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = PromptTemplateService(session)
        items, total = await svc.list_templates(
            category=category, locale=locale, enabled=enabled,
            offset=offset, limit=min(limit, 100),
        )
        return TemplateListResponse(items=items, total=total)


@router.get("/search/by-name", response_model=TemplateResponse)
async def get_template_by_name(name: str, request: Request):
    """根据名称查询模板。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = PromptTemplateService(session)
        tpl = await svc.get_by_name(name)
        if not tpl:
            raise HTTPException(status_code=404, detail=f"Template '{name}' not found")
        return tpl


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str, request: Request):
    """根据 ID 查询模板。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = PromptTemplateService(session)
        tpl = await svc.get_by_id(UUID(template_id))
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")
        return tpl


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(template_id: str, body: TemplateUpdate, request: Request):
    """更新模板。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = PromptTemplateService(session)
        # 如果更新名称，检查唯一性
        if body.name is not None:
            existing = await svc.get_by_name(body.name)
            if existing and str(existing.id) != template_id:
                raise HTTPException(status_code=409, detail=f"Template '{body.name}' already exists")
        tpl = await svc.update(
            UUID(template_id),
            name=body.name,
            content=body.content,
            category=body.category,
            locale=body.locale,
            enabled=body.enabled,
        )
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")
        return tpl


@router.delete("/{template_id}", status_code=204)
async def delete_template(template_id: str, request: Request):
    """删除模板。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = PromptTemplateService(session)
        deleted = await svc.delete(UUID(template_id))
        if not deleted:
            raise HTTPException(status_code=404, detail="Template not found")


# ---- 项目绑定管理端点 ----

@binding_router.get("", response_model=list[PromptBindingResponse])
async def list_project_bindings(
    request: Request,
    project_id: UUID,
):
    """获取项目的 Prompt 模板绑定列表。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = PromptTemplateService(session)
        bindings = await svc.list_bindings(project_id)

        result = []
        for binding in bindings:
            tpl = await svc.get_by_id(binding.template_id)
            result.append(
                PromptBindingResponse(
                    id=binding.id,
                    project_id=binding.project_id,
                    template_id=binding.template_id,
                    template=TemplateResponse.model_validate(tpl) if tpl else None,
                    is_default=binding.is_default,
                    priority=binding.priority,
                    enabled=binding.enabled,
                    created_at=binding.created_at,
                )
            )
        return result


@binding_router.post("", response_model=PromptBindingResponse, status_code=status.HTTP_201_CREATED)
async def create_binding(
    request: Request,
    project_id: UUID,
    data: PromptBindingCreate,
):
    """为项目添加 Prompt 模板绑定。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = PromptTemplateService(session)
        try:
            binding = await svc.create_binding(
                project_id=project_id,
                template_id=data.template_id,
                is_default=data.is_default,
                priority=data.priority,
            )
            await session.commit()
            await session.refresh(binding)

            tpl = await svc.get_by_id(binding.template_id)
            return PromptBindingResponse(
                id=binding.id,
                project_id=binding.project_id,
                template_id=binding.template_id,
                template=TemplateResponse.model_validate(tpl) if tpl else None,
                is_default=binding.is_default,
                priority=binding.priority,
                enabled=binding.enabled,
                created_at=binding.created_at,
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@binding_router.put("/{binding_id}", response_model=PromptBindingResponse)
async def update_binding(
    request: Request,
    project_id: UUID,
    binding_id: UUID,
    data: PromptBindingUpdate,
):
    """更新绑定配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = PromptTemplateService(session)
        try:
            update_data = {k: v for k, v in data.model_dump().items() if v is not None}
            binding = await svc.update_binding(binding_id, **update_data)
            await session.commit()
            await session.refresh(binding)

            tpl = await svc.get_by_id(binding.template_id)
            return PromptBindingResponse(
                id=binding.id,
                project_id=binding.project_id,
                template_id=binding.template_id,
                template=TemplateResponse.model_validate(tpl) if tpl else None,
                is_default=binding.is_default,
                priority=binding.priority,
                enabled=binding.enabled,
                created_at=binding.created_at,
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@binding_router.delete("/{binding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_binding(
    request: Request,
    project_id: UUID,
    binding_id: UUID,
):
    """删除绑定。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = PromptTemplateService(session)
        try:
            await svc.delete_binding(binding_id)
            await session.commit()
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@binding_router.patch("/{binding_id}/set-default", response_model=PromptBindingResponse)
async def set_default_binding(
    request: Request,
    project_id: UUID,
    binding_id: UUID,
):
    """设置默认模板。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = PromptTemplateService(session)
        try:
            binding = await svc.set_default_binding(binding_id)
            await session.commit()
            await session.refresh(binding)

            tpl = await svc.get_by_id(binding.template_id)
            return PromptBindingResponse(
                id=binding.id,
                project_id=binding.project_id,
                template_id=binding.template_id,
                template=TemplateResponse.model_validate(tpl) if tpl else None,
                is_default=binding.is_default,
                priority=binding.priority,
                enabled=binding.enabled,
                created_at=binding.created_at,
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
