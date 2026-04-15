"""FastAPI 应用入口。"""

import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from code_review.api.webhook import router as webhook_router
from code_review.api.management import router as management_router
from code_review.api.prompt_template import router as prompt_template_router
from code_review.infrastructure.celery_app import init_celery
from code_review.infrastructure.notification_manager import NotificationManager
from code_review.models.config import AppConfig
from code_review.models.db import Base
from code_review.services.review_orchestrator import ReviewOrchestrator
from code_review.services.prompt_template_service import seed_default_templates

logger = structlog.get_logger()


def setup_logging(log_level: str = "INFO") -> None:
    """配置结构化日志。"""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def create_app(config: AppConfig | None = None) -> FastAPI:
    """创建 FastAPI 应用实例。"""
    if config is None:
        config = AppConfig()

    setup_logging(config.server.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """应用生命周期管理。"""
        logger.info("Starting code review service...")

        # 初始化数据库
        engine = create_async_engine(
            config.database.url,
            echo=config.database.echo,
            pool_size=config.database.pool_size,
        )
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # 种子默认 Prompt 模板
        async with session_factory() as seed_session:
            await seed_default_templates(seed_session)

        # 初始化 Celery
        init_celery(config)

        # 初始化编排器
        orchestrator = ReviewOrchestrator(config)
        notification_manager = NotificationManager(config)

        # 注入到 app.state
        app.state.config = config
        app.state.session_factory = session_factory
        app.state.orchestrator = orchestrator
        app.state.notification_manager = notification_manager
        app.state.engine = engine

        logger.info("Service started successfully")
        yield

        # 清理
        logger.info("Shutting down...")
        await orchestrator.close()
        await engine.dispose()

    app = FastAPI(
        title="Code Review Service",
        description="AI-powered code review service for GitHub, GitLab, and Gitee",
        version="1.0.0",
        lifespan=lifespan,
    )

    # 注册路由
    app.include_router(webhook_router)
    app.include_router(management_router)
    app.include_router(prompt_template_router)

    return app


# WSGI/ASGI 入口
app = create_app()
