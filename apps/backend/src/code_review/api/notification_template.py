"""通知模板 REST API 端点。"""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from code_review.models.db import NotificationTemplate, ProjectNotificationTemplateBinding
from code_review.services.notification_template_service import NotificationTemplateService

logger = logging.getLogger(__name__)

# 模板 CRUD 路由
router = APIRouter(prefix="/api/v1/notification-templates", tags=["notification-templates"])

# 渠道默认模板路由（挂在 notification-configs 前缀下）
channel_router = APIRouter(prefix="/api/v1/notification-configs", tags=["notification-configs"])

# 项目级绑定路由（挂在 projects 前缀下）
binding_router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


# ---- 请求/响应模型 ----

class TemplateCreate(BaseModel):
    """创建模板请求体。"""
    name: str = Field(..., min_length=1, max_length=128)
    channel: str = Field(..., min_length=1, max_length=32)
    title_template: str = Field(..., min_length=1, max_length=512)
    body_template: str = Field(..., min_length=1)
    description: str = ""
    enabled: bool = True


class TemplateUpdate(BaseModel):
    """更新模板请求体（所有字段可选）。"""
    name: str | None = Field(None, min_length=1, max_length=128)
    title_template: str | None = Field(None, min_length=1, max_length=512)
    body_template: str | None = None
    description: str | None = None
    enabled: bool | None = None


class TemplateResponse(BaseModel):
    """模板响应模型。"""
    id: UUID
    name: str
    channel: str
    description: str
    title_template: str
    body_template: str
    enabled: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PreviewRequest(BaseModel):
    """模板预览请求体，传入示例变量值。"""
    mr_title: str = "feat: 新增登录功能"
    mr_author: str = "zhangsan"
    project_name: str = "backend-api"
    critical_count: int = 0
    warning_count: int = 1
    suggestion_count: int = 3
    info_count: int = 0
    summary: str = "本次 MR 整体质量良好，存在少量警告，建议关注。"
    mr_url: str = "https://gitee.com/example/repo/pulls/1"


class PreviewResponse(BaseModel):
    """模板预览响应体。"""
    title: str
    body: str


class ChannelTemplateRequest(BaseModel):
    """设置渠道默认模板请求体。"""
    template_id: UUID | None = None


class ProjectBindingItem(BaseModel):
    """项目绑定条目。"""
    notification_id: UUID
    template_id: UUID | None = None
    enabled: bool = True


class ProjectBindingResponse(BaseModel):
    """项目绑定响应条目。"""
    id: UUID
    project_id: UUID
    notification_id: UUID
    template_id: UUID | None
    enabled: bool
    created_at: datetime

    # 冗余字段，方便前端展示
    channel: str | None = None
    template_name: str | None = None

    model_config = {"from_attributes": True}


def _to_response(tpl: NotificationTemplate) -> TemplateResponse:
    """ORM 对象转响应模型。"""
    return TemplateResponse(
        id=tpl.id,
        name=tpl.name,
        channel=tpl.channel,
        description=tpl.description,
        title_template=tpl.title_template,
        body_template=tpl.body_template,
        enabled=tpl.enabled,
        is_default=tpl.is_default,
        created_at=tpl.created_at,
        updated_at=tpl.updated_at,
    )


# ---- 模板 CRUD 端点 ----

@router.get("", response_model=list[TemplateResponse])
async def list_templates(
    request: Request,
    channel: str | None = Query(None, description="按渠道过滤：dingtalk / feishu"),
):
    """查询通知模板列表，可按渠道过滤。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = NotificationTemplateService(session)
        templates = await svc.get_all(channel=channel)
        return [_to_response(t) for t in templates]


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: UUID, request: Request):
    """查询指定模板详情。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = NotificationTemplateService(session)
        tpl = await svc.get_by_id(template_id)
        if tpl is None:
            raise HTTPException(status_code=404, detail=f"模板 '{template_id}' 不存在")
        return _to_response(tpl)


@router.post("", response_model=TemplateResponse, status_code=201)
async def create_template(body: TemplateCreate, request: Request):
    """创建新通知模板。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = NotificationTemplateService(session)
        tpl = await svc.create(
            name=body.name,
            channel=body.channel,
            title_template=body.title_template,
            body_template=body.body_template,
            description=body.description,
            enabled=body.enabled,
        )
        return _to_response(tpl)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(template_id: UUID, body: TemplateUpdate, request: Request):
    """更新通知模板。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = NotificationTemplateService(session)
        update_data = {k: v for k, v in body.model_dump().items() if v is not None}
        tpl = await svc.update(template_id, **update_data)
        if tpl is None:
            raise HTTPException(status_code=404, detail=f"模板 '{template_id}' 不存在")
        return _to_response(tpl)


@router.delete("/{template_id}", status_code=204)
async def delete_template(template_id: UUID, request: Request):
    """删除通知模板（内置默认模板不可删除）。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = NotificationTemplateService(session)
        try:
            deleted = await svc.delete(template_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if not deleted:
            raise HTTPException(status_code=404, detail=f"模板 '{template_id}' 不存在")


@router.post("/{template_id}/preview", response_model=PreviewResponse)
async def preview_template(template_id: UUID, body: PreviewRequest, request: Request):
    """预览模板渲染效果，传入示例变量值，返回渲染后的标题和正文。"""
    from code_review.core.notification import NotificationPayload
    from code_review.infrastructure.notification_renderer import NotificationRenderer

    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = NotificationTemplateService(session)
        tpl = await svc.get_by_id(template_id)
        if tpl is None:
            raise HTTPException(status_code=404, detail=f"模板 '{template_id}' 不存在")

    # 用请求体中的示例值构造 payload
    payload = NotificationPayload(
        mr_title=body.mr_title,
        mr_author=body.mr_author,
        mr_url=body.mr_url,
        project_name=body.project_name,
        summary=body.summary,
        critical_count=body.critical_count,
        warning_count=body.warning_count,
        suggestion_count=body.suggestion_count,
        info_count=body.info_count,
    )

    rendered_title, rendered_body = NotificationRenderer.render(
        tpl.title_template,
        tpl.body_template,
        payload,
    )

    return PreviewResponse(title=rendered_title, body=rendered_body)


# ---- 渠道默认模板端点 ----

@channel_router.put("/{channel}/template")
async def set_channel_template(channel: str, body: ChannelTemplateRequest, request: Request):
    """设置指定渠道的默认模板（传 null 则清除绑定）。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = NotificationTemplateService(session)
        try:
            nc = await svc.set_channel_default_template(channel, body.template_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if nc is None:
            raise HTTPException(status_code=404, detail=f"渠道 '{channel}' 不存在")
        return {
            "channel": channel,
            "template_id": str(nc.template_id) if nc.template_id else None,
        }


# ---- 项目级绑定端点 ----

@binding_router.get("/{project_id}/notification-template-bindings", response_model=list[ProjectBindingResponse])
async def get_project_notification_bindings(project_id: UUID, request: Request):
    """查询项目的通知模板绑定列表。"""
    from sqlalchemy import select
    from code_review.models.db import NotificationConfig

    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = NotificationTemplateService(session)
        bindings = await svc.get_project_bindings(project_id)
        return await _enrich_bindings(session, bindings)


@binding_router.put("/{project_id}/notification-template-bindings", response_model=list[ProjectBindingResponse])
async def upsert_project_notification_bindings(
    project_id: UUID,
    body: list[ProjectBindingItem],
    request: Request,
):
    """批量设置项目的通知模板绑定（upsert：已存在则更新，不存在则创建）。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = NotificationTemplateService(session)
        bindings_data = [item.model_dump() for item in body]
        bindings = await svc.upsert_project_bindings(project_id, bindings_data)
        return await _enrich_bindings(session, bindings)


async def _enrich_bindings(
    session, bindings: list[ProjectNotificationTemplateBinding]
) -> list[ProjectBindingResponse]:
    """批量查询关联的渠道和模板名称，避免 N+1。"""
    from sqlalchemy import select
    from code_review.models.db import NotificationConfig, NotificationTemplate as NT

    notification_ids = [b.notification_id for b in bindings]
    template_ids = [b.template_id for b in bindings if b.template_id]

    nc_map: dict[UUID, str] = {}
    if notification_ids:
        result = await session.execute(
            select(NotificationConfig).where(NotificationConfig.id.in_(notification_ids))
        )
        nc_map = {nc.id: nc.channel for nc in result.scalars().all()}

    tpl_map: dict[UUID, str] = {}
    if template_ids:
        result = await session.execute(
            select(NT).where(NT.id.in_(template_ids))
        )
        tpl_map = {t.id: t.name for t in result.scalars().all()}

    return [
        ProjectBindingResponse(
            id=b.id,
            project_id=b.project_id,
            notification_id=b.notification_id,
            template_id=b.template_id,
            enabled=b.enabled,
            created_at=b.created_at,
            channel=nc_map.get(b.notification_id),
            template_name=tpl_map.get(b.template_id) if b.template_id else None,
        )
        for b in bindings
    ]
