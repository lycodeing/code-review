"""系统健康检查 API 端点。"""

import structlog
from fastapi import APIRouter, Request
from sqlalchemy import select, func

from code_review.models.db import Project

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def health_check(request: Request):
    """系统健康检查。"""
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
