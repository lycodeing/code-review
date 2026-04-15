"""平台配置 REST API 端点。"""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from code_review.infrastructure.config_crypto import mask_value
from code_review.models.db import PlatformConfig
from code_review.services.platform_config_service import PlatformConfigService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/platform-configs", tags=["platform-configs"])

MASKED_FIELDS = {"access_token", "webhook_secret"}


# ---- 请求/响应模型 ----

class PlatformCreate(BaseModel):
    platform: str = Field(..., min_length=1, max_length=32)
    access_token: str = ""
    webhook_secret: str = ""
    api_url: str = ""
    enabled: bool = True
    description: str = ""


class PlatformUpdate(BaseModel):
    access_token: str | None = None
    webhook_secret: str | None = None
    api_url: str | None = None
    enabled: bool | None = None
    description: str | None = None


class PlatformResponse(BaseModel):
    id: UUID
    platform: str
    access_token: str
    webhook_secret: str
    api_url: str
    enabled: bool
    description: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BindingItem(BaseModel):
    channel: str
    enabled: bool


class PlatformDetailResponse(PlatformResponse):
    notifications: list[BindingItem] = []


class ImportRequest(BaseModel):
    overwrite: bool = False
    configs: list[dict]


class ImportResponse(BaseModel):
    imported: int
    skipped: int
    errors: list[str]


def _mask_config(pc: PlatformConfig) -> PlatformResponse:
    """敏感字段脱敏。"""
    data = {
        "id": pc.id,
        "platform": pc.platform,
        "access_token": mask_value(pc.access_token),
        "webhook_secret": mask_value(pc.webhook_secret),
        "api_url": pc.api_url,
        "enabled": pc.enabled,
        "description": pc.description,
        "created_at": pc.created_at,
        "updated_at": pc.updated_at,
    }
    return PlatformResponse(**data)


def _get_service(request: Request) -> PlatformConfigService:
    return PlatformConfigService(
        request.app.state.session_factory(),
        secret_key=request.app.state.config.server.secret_key,
    )


# ---- 端点 ----

@router.get("", response_model=list[PlatformResponse])
async def list_platform_configs(request: Request):
    """查询所有平台配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = PlatformConfigService(session, request.app.state.config.server.secret_key)
        configs = await svc.get_all()
        return [_mask_config(pc) for pc in configs]


@router.get("/{platform}", response_model=PlatformDetailResponse)
async def get_platform_config(platform: str, request: Request):
    """按平台标识查询配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = PlatformConfigService(session, request.app.state.config.server.secret_key)
        pc = await svc.get_by_platform(platform)
        if not pc:
            raise HTTPException(status_code=404, detail=f"Platform '{platform}' not found")

        # 查询绑定的通知渠道
        notifications = await svc.get_bound_notifications(platform)

        return PlatformDetailResponse(
            id=pc.id,
            platform=pc.platform,
            access_token=mask_value(pc.access_token),
            webhook_secret=mask_value(pc.webhook_secret),
            api_url=pc.api_url,
            enabled=pc.enabled,
            description=pc.description,
            created_at=pc.created_at,
            updated_at=pc.updated_at,
            notifications=[
                BindingItem(channel=nc.channel, enabled=nc.enabled)
                for nc in notifications
            ],
        )


@router.post("", response_model=PlatformResponse, status_code=201)
async def create_platform_config(body: PlatformCreate, request: Request):
    """创建平台配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = PlatformConfigService(session, request.app.state.config.server.secret_key)
        existing = await svc.get_by_platform(body.platform)
        if existing:
            raise HTTPException(status_code=409, detail=f"Platform '{body.platform}' already exists")
        pc = await svc.create(
            platform=body.platform,
            access_token=body.access_token,
            webhook_secret=body.webhook_secret,
            api_url=body.api_url,
            enabled=body.enabled,
            description=body.description,
        )
        return _mask_config(pc)


@router.put("/{platform}", response_model=PlatformResponse)
async def update_platform_config(platform: str, body: PlatformUpdate, request: Request):
    """更新平台配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = PlatformConfigService(session, request.app.state.config.server.secret_key)
        pc = await svc.update(
            platform,
            **{k: v for k, v in body.model_dump().items() if v is not None},
        )
        if not pc:
            raise HTTPException(status_code=404, detail=f"Platform '{platform}' not found")
        return _mask_config(pc)


@router.delete("/{platform}", status_code=204)
async def delete_platform_config(platform: str, request: Request):
    """删除平台配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = PlatformConfigService(session, request.app.state.config.server.secret_key)
        deleted = await svc.delete(platform)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Platform '{platform}' not found")


@router.post("/import", response_model=ImportResponse)
async def import_platform_configs(body: ImportRequest, request: Request):
    """批量导入平台配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = PlatformConfigService(session, request.app.state.config.server.secret_key)
        result = await svc.batch_import(body.configs, overwrite=body.overwrite)
        return ImportResponse(**result)
