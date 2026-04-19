"""API 调用日志查询端点。"""

import logging
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, func
from datetime import datetime

from code_review.models.db import ApiCallLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["logs"])


class ApiCallLogResponse(BaseModel):
    id: UUID
    task_id: UUID | None
    call_type: str
    provider: str | None
    method: str | None
    url: str | None
    request_headers: dict | None
    request_body: dict | None
    response_status: int | None
    response_body: dict | None
    status: str
    error_message: str | None
    duration_ms: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedLogsResponse(BaseModel):
    items: list[ApiCallLogResponse]
    total: int


@router.get("/logs", response_model=PaginatedLogsResponse)
async def list_api_call_logs(
    request: Request,
    call_type: str | None = None,
    status: str | None = None,
    task_id: UUID | None = None,
    provider: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """查询全局 API 调用日志，支持按类型、状态、任务、提供商过滤，返回真实总数。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        base_filter = []
        if call_type:
            base_filter.append(ApiCallLog.call_type == call_type)
        if status:
            base_filter.append(ApiCallLog.status == status)
        if task_id:
            base_filter.append(ApiCallLog.task_id == task_id)
        if provider:
            base_filter.append(ApiCallLog.provider.ilike(f"%{provider}%"))

        total_stmt = select(func.count()).select_from(ApiCallLog).where(*base_filter)
        total = (await session.execute(total_stmt)).scalar_one()

        items_stmt = (
            select(ApiCallLog)
            .where(*base_filter)
            .order_by(ApiCallLog.created_at.desc())
            .offset(offset)
            .limit(min(limit, 200))
        )
        result = await session.execute(items_stmt)
        items = result.scalars().all()

    return PaginatedLogsResponse(items=items, total=total)
