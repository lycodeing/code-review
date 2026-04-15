"""Celery Worker 入口。

启动方式：celery -A code_review.worker worker -Q review -l info
"""

import asyncio
import os

from code_review.infrastructure.celery_app import init_celery, get_celery
from code_review.models.config import AppConfig
from code_review.services.review_orchestrator import ReviewOrchestrator

# 初始化 Celery
config = AppConfig()
celery_app = init_celery(config)


@celery_app.task(name="code_review.execute_review", bind=True, max_retries=2)
def execute_review_task(self, task_id: str) -> None:
    """Celery 任务：执行代码评审。

    每次任务创建新的 orchestrator，避免跨事件循环问题。
    """
    task_config = AppConfig()
    orchestrator = ReviewOrchestrator(task_config)
    asyncio.run(orchestrator.execute_review(task_id))
