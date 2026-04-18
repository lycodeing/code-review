"""通知渠道配置 REST API 端点。"""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from code_review.infrastructure.config_crypto import mask_value
from code_review.models.db import NotificationConfig
from code_review.services.notification_config_service import NotificationConfigService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/notification-configs", tags=["notification-configs"])


# ---- 请求/响应模型 ----

class NotificationCreate(BaseModel):
    channel: str = Field(..., min_length=1, max_length=32)
    enabled: bool = False
    webhook_url: str = ""
    secret: str = ""
    at_mobiles: str = ""
    description: str = ""


class NotificationUpdate(BaseModel):
    enabled: bool | None = None
    webhook_url: str | None = None
    secret: str | None = None
    at_mobiles: str | None = None
    description: str | None = None


class NotificationResponse(BaseModel):
    id: UUID
    channel: str
    enabled: bool
    webhook_url: str
    secret: str
    at_mobiles: str
    description: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BindingRequest(BaseModel):
    platform: str
    enabled: bool = True


class BindingResponse(BaseModel):
    platform: str
    enabled: bool


class NotificationDetailResponse(NotificationResponse):
    platforms: list[BindingResponse] = []


class ImportRequest(BaseModel):
    overwrite: bool = False
    configs: list[dict]


class ImportResponse(BaseModel):
    imported: int
    skipped: int
    errors: list[str]


def _mask_config(nc: NotificationConfig) -> NotificationResponse:
    """敏感字段脱敏。"""
    return NotificationResponse(
        id=nc.id,
        channel=nc.channel,
        enabled=nc.enabled,
        webhook_url=nc.webhook_url,
        secret=mask_value(nc.secret),
        at_mobiles=nc.at_mobiles,
        description=nc.description,
        created_at=nc.created_at,
        updated_at=nc.updated_at,
    )


# ---- 端点 ----

@router.get("", response_model=list[NotificationResponse])
async def list_notification_configs(request: Request):
    """查询所有通知渠道配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = NotificationConfigService(session, request.app.state.config.server.secret_key)
        configs = await svc.get_all()
        return [_mask_config(nc) for nc in configs]


@router.get("/{channel}", response_model=NotificationDetailResponse)
async def get_notification_config(channel: str, request: Request):
    """按渠道标识查询配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = NotificationConfigService(session, request.app.state.config.server.secret_key)
        nc = await svc.get_by_channel(channel)
        if not nc:
            raise HTTPException(status_code=404, detail=f"Channel '{channel}' not found")

        # 查询关联的平台
        from sqlalchemy import select
        from code_review.models.db import PlatformNotificationBinding, PlatformConfig
        stmt = (
            select(PlatformConfig, PlatformNotificationBinding.enabled)
            .join(PlatformNotificationBinding, PlatformNotificationBinding.platform_id == PlatformConfig.id)
            .where(PlatformNotificationBinding.notification_id == nc.id)
        )
        result = await session.execute(stmt)
        rows = result.all()

        return NotificationDetailResponse(
            id=nc.id,
            channel=nc.channel,
            enabled=nc.enabled,
            webhook_url=nc.webhook_url,
            secret=mask_value(nc.secret),
            at_mobiles=nc.at_mobiles,
            description=nc.description,
            created_at=nc.created_at,
            updated_at=nc.updated_at,
            platforms=[
                BindingResponse(platform=pc.platform, enabled=bind_enabled)
                for pc, bind_enabled in rows
            ],
        )


@router.post("", response_model=NotificationResponse, status_code=201)
async def create_notification_config(body: NotificationCreate, request: Request):
    """创建通知渠道配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = NotificationConfigService(session, request.app.state.config.server.secret_key)
        existing = await svc.get_by_channel(body.channel)
        if existing:
            raise HTTPException(status_code=409, detail=f"Channel '{body.channel}' already exists")
        nc = await svc.create(
            channel=body.channel,
            enabled=body.enabled,
            webhook_url=body.webhook_url,
            secret=body.secret,
            at_mobiles=body.at_mobiles,
            description=body.description,
        )
        return _mask_config(nc)


@router.put("/{channel}", response_model=NotificationResponse)
async def update_notification_config(channel: str, body: NotificationUpdate, request: Request):
    """更新通知渠道配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = NotificationConfigService(session, request.app.state.config.server.secret_key)
        nc = await svc.update(
            channel,
            **{k: v for k, v in body.model_dump().items() if v is not None},
        )
        if not nc:
            raise HTTPException(status_code=404, detail=f"Channel '{channel}' not found")
        return _mask_config(nc)


@router.delete("/{channel}", status_code=204)
async def delete_notification_config(channel: str, request: Request):
    """删除通知渠道配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = NotificationConfigService(session, request.app.state.config.server.secret_key)
        deleted = await svc.delete(channel)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Channel '{channel}' not found")


@router.post("/import", response_model=ImportResponse)
async def import_notification_configs(body: ImportRequest, request: Request):
    """批量导入通知渠道配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = NotificationConfigService(session, request.app.state.config.server.secret_key)
        result = await svc.batch_import(body.configs, overwrite=body.overwrite)
        return ImportResponse(**result)


@router.put("/{channel}/bindings")
async def set_binding(channel: str, body: BindingRequest, request: Request):
    """设置平台-通知渠道绑定关系。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = NotificationConfigService(session, request.app.state.config.server.secret_key)
        binding = await svc.set_binding(
            platform=body.platform,
            channel=channel,
            enabled=body.enabled,
        )
        if not binding:
            raise HTTPException(status_code=404, detail="Platform or channel not found")
        return {"platform": body.platform, "channel": channel, "enabled": body.enabled}
