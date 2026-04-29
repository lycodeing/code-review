"""Celery Worker 入口。

启动方式：celery -A code_review.worker worker -Q review -l info
"""

import asyncio

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from code_review.core.errors import RetryableError
from code_review.infrastructure.celery_app import init_celery, get_celery
from code_review.models.config import AppConfig
from code_review.services.review_orchestrator import ReviewOrchestrator

# 初始化 Celery
config = AppConfig()
celery_app = init_celery(config)


async def _run_review(task_id: str) -> None:
    """在单个事件循环中执行评审并释放连接池。"""
    task_config = AppConfig()
    engine = create_async_engine(
        task_config.database.url,
        echo=task_config.database.echo,
        pool_size=task_config.database.pool_size,
    )
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        orchestrator = ReviewOrchestrator(
            task_config,
            session_factory=session_factory,
            secret_key=task_config.server.secret_key,
        )
        await orchestrator.execute_review(task_id)
    finally:
        await engine.dispose()


@celery_app.task(
    name="code_review.execute_review",
    bind=True,
    max_retries=3,
    autoretry_for=(RetryableError,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def execute_review_task(self, task_id: str) -> None:
    """Celery 任务：执行代码评审。支持对 RetryableError 自动重试。"""
    asyncio.run(_run_review(task_id))