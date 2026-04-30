"""系统配置 REST API 端点。"""

import logging

from fastapi import APIRouter, HTTPException, Request

from code_review.schemas.system_settings import (
    CATEGORY_LABELS,
    CategoryResponse,
    SystemSettingBatchUpdate,
    SystemSettingResponse,
)
from code_review.services.system_settings_service import SystemSettingsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/system-settings", tags=["system-settings"])


@router.get("", response_model=list[SystemSettingResponse])
async def list_settings(request: Request):
    """获取全部系统配置。"""
    async with request.app.state.session_factory() as session:
        svc = SystemSettingsService(session)
        return await svc.get_all()


@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(request: Request):
    """获取所有配置分类。"""
    async with request.app.state.session_factory() as session:
        svc = SystemSettingsService(session)
        rows = await svc.get_categories()
        return [
            CategoryResponse(
                key=r["key"],
                label=CATEGORY_LABELS.get(r["key"], r["key"]),
                count=r["count"],
            )
            for r in rows
        ]


@router.get("/category/{category}", response_model=list[SystemSettingResponse])
async def list_settings_by_category(category: str, request: Request):
    """按分类获取系统配置。"""
    async with request.app.state.session_factory() as session:
        svc = SystemSettingsService(session)
        settings = await svc.get_by_category(category)
        if not settings:
            raise HTTPException(status_code=404, detail=f"分类 '{category}' 下无配置项")
        return settings


@router.put("", response_model=list[SystemSettingResponse])
async def batch_update_settings(body: SystemSettingBatchUpdate, request: Request):
    """批量更新系统配置。"""
    async with request.app.state.session_factory() as session:
        svc = SystemSettingsService(session)
        items = [{"key": item.key, "value": item.value} for item in body.settings]
        return await svc.update_batch(items)
