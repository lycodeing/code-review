"""API 调用日志写入工具函数，供各 reviewer 和通知渠道共享。"""

import logging
from uuid import UUID

logger = logging.getLogger(__name__)


async def save_llm_log(
    session_factory,
    task_id: UUID,
    *,
    provider: str,
    url: str,
    request_body: dict,
    response_status: int,
    response_body: dict,
    status: str,
    error_message: str | None,
    duration_ms: int,
) -> None:
    """将 LLM 调用结果写入 api_call_logs 表。"""
    try:
        from code_review.models.db import ApiCallLog
        async with session_factory() as session:
            log = ApiCallLog(
                task_id=task_id,
                call_type=ApiCallLog.CallType.LLM,
                provider=provider,
                method="POST",
                url=url,
                request_headers={"Authorization": "[REDACTED]", "Content-Type": "application/json"},
                request_body=request_body,
                response_status=response_status,
                response_body=response_body,
                status=status,
                error_message=error_message,
                duration_ms=duration_ms,
            )
            session.add(log)
            await session.commit()
    except Exception as e:
        logger.warning("记录 LLM 调用日志失败: %s", e)
