"""Celery Worker 入口。

启动方式：celery -A code_review.worker worker -Q review -l info
"""

import asyncio

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from code_review.infrastructure.celery_app import init_celery, get_celery
from code_review.models.config import AppConfig
from code_review.services.review_orchestrator import ReviewOrchestrator

# 初始化 Celery
config = AppConfig()
celery_app = init_celery(config)


def _create_session_factory():
    """创建当前事件循环的 session factory。"""
    engine = create_async_engine(
        config.database.url,
        echo=config.database.echo,
        pool_size=config.database.pool_size,
    )
    return async_sessionmaker(engine, expire_on_commit=False)


@celery_app.task(name="code_review.execute_review", bind=True, max_retries=2)
def execute_review_task(self, task_id: str) -> None:
    """Celery 任务：执行代码评审。

    每次任务创建新的 orchestrator，避免跨事件循环问题。
    """
    task_config = AppConfig()
    session_factory = _create_session_factory()
    orchestrator = ReviewOrchestrator(
        task_config,
        session_factory=session_factory,
        secret_key=task_config.server.secret_key,
    )
    asyncio.run(orchestrator.execute_review(task_id))
