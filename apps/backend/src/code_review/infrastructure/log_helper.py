"""API 调用日志写入工具函数，供各 reviewer 和通知渠道共享。"""

import logging
from uuid import UUID

from code_review.models.db import ApiCallLog

logger = logging.getLogger(__name__)


async def create_llm_log(
    session_factory,
    task_id: UUID,
    *,
    provider: str,
    url: str,
    request_body: dict,
) -> UUID:
    """在 LLM 调用发起前创建一条 in_progress 日志记录，返回日志 ID。"""
    try:
        async with session_factory() as session:
            log = ApiCallLog(
                task_id=task_id,
                call_type=ApiCallLog.CallType.LLM,
                provider=provider,
                method="POST",
                url=url,
                request_headers={"Authorization": "[REDACTED]", "Content-Type": "application/json"},
                request_body=request_body,
                status=ApiCallLog.CallStatus.IN_PROGRESS,
            )
            session.add(log)
            await session.commit()
            return log.id
    except Exception as e:
        logger.warning("创建 LLM 调用日志失败: %s", e)
        return UUID(int=0)


async def update_llm_log(
    session_factory,
    log_id: UUID,
    *,
    response_status: int,
    response_body: dict,
    status: str,
    error_message: str | None,
    duration_ms: int,
) -> None:
    """LLM 调用完成后更新已有的日志记录。"""
    if log_id == UUID(int=0):
        return
    try:
        async with session_factory() as session:
            log = await session.get(ApiCallLog, log_id)
            if log:
                log.response_status = response_status
                log.response_body = response_body
                log.status = status
                log.error_message = error_message
                log.duration_ms = duration_ms
                await session.commit()
    except Exception as e:
        logger.warning("更新 LLM 调用日志失败: %s", e)


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
    """一次性写入 LLM 调用日志（兼容旧调用方式）。"""
    try:
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
