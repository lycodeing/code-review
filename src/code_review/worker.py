"""Celery Worker 入口。

启动方式：celery -A code_review.worker worker -Q review -l info
"""

import asyncio
import os

from code_review.infrastructure.celery_app import init_celery, get_celery
from code_review.models.config import AppConfig
from code_review.services.review_orchestrator import ReviewOrchestrator

# 全局编排器实例
_orchestrator: ReviewOrchestrator | None = None


def _get_orchestrator() -> ReviewOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        config = AppConfig()
        _orchestrator = ReviewOrchestrator(config)
    return _orchestrator


# 初始化 Celery
config = AppConfig()
celery_app = init_celery(config)


@celery_app.task(name="code_review.execute_review", bind=True, max_retries=2)
def execute_review_task(self, task_id: str) -> None:
    """Celery 任务：执行代码评审。"""
    orchestrator = _get_orchestrator()
    asyncio.run(orchestrator.execute_review(task_id))
