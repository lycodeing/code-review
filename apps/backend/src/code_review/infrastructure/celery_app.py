"""Celery 异步任务定义。"""

import asyncio
import logging
from functools import wraps

from celery import Celery

from code_review.models.config import AppConfig

logger = logging.getLogger(__name__)

# 全局 Celery 应用实例，由应用启动时初始化
celery_app: Celery | None = None


def init_celery(config: AppConfig) -> Celery:
    """初始化 Celery 应用。"""
    global celery_app
    celery_app = Celery(
        "code_review",
        broker=config.celery.broker_url,
        backend=config.celery.result_backend,
    )
    celery_app.conf.update(
        task_serializer=config.celery.task_serializer,
        result_serializer=config.celery.result_serializer,
        timezone=config.celery.timezone,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_soft_time_limit=300,  # 5 分钟软超时
        task_time_limit=600,  # 10 分钟硬超时
    )
    return celery_app


def get_celery() -> Celery:
    """获取 Celery 应用实例。"""
    if celery_app is None:
        raise RuntimeError("Celery not initialized. Call init_celery() first.")
    return celery_app


def async_task(func):
    """装饰器：将 async 函数包装为 Celery 任务。

    由于 Celery 原生不支持 async，此装饰器在 worker 中自动运行事件循环。
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    app = get_celery()
    return app.task(wrapper, name=f"code_review.{func.__name__}")


# ---- 任务定义 ----
# 注意：实际任务在 services/review_orchestrator.py 中定义
# 这里注册任务名称，确保 Celery 能发现
