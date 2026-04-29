"""FastAPI 应用入口。"""

import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from code_review.api.webhook import router as webhook_router
from code_review.api.projects import router as projects_router
from code_review.api.reviews import router as reviews_router
from code_review.api.prompt_template import router as prompt_template_router, binding_router as prompt_binding_router
from code_review.api.platform_config import router as platform_config_router
from code_review.api.notification_config import router as notification_config_router
from code_review.api.notification_template import (
    router as notification_template_router,
    channel_router as notification_channel_template_router,
    binding_router as notification_template_binding_router,
)
from code_review.api.llm_config import router as llm_config_router, binding_router as llm_binding_router
from code_review.api.dashboard import router as dashboard_router
from code_review.api.logs import router as logs_router
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
        # 启动时检测弱默认密钥
        if config.server.secret_key == "change-me-in-production":
            logger.warning(
                "⚠️  SERVER__SECRET_KEY 使用默认弱密钥，生产环境必须修改！"
                " 请设置环境变量 CODE_REVIEW__SERVER__SECRET_KEY"
            )

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

        # 种子默认平台和通知配置
        async with session_factory() as seed_session:
            await _seed_config_tables(seed_session)

        # 初始化 Celery
        init_celery(config)

        # 初始化编排器（传入 session_factory 和 secret_key 以支持 DB 配置）
        orchestrator = ReviewOrchestrator(
            config,
            session_factory=session_factory,
            secret_key=config.server.secret_key,
        )
        notification_manager = NotificationManager(config)

        # 从 DB 初始化通知渠道
        await notification_manager.init_channels_from_db(
            session_factory, config.server.secret_key,
        )

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
    app.include_router(projects_router)
    app.include_router(reviews_router)
    app.include_router(prompt_template_router)
    app.include_router(platform_config_router)
    app.include_router(notification_config_router)
    app.include_router(notification_template_router)
    app.include_router(notification_channel_template_router)
    app.include_router(notification_template_binding_router)
    app.include_router(llm_config_router)
    app.include_router(llm_binding_router)
    app.include_router(prompt_binding_router)
    app.include_router(logs_router)
    app.include_router(dashboard_router)

    # 根路径重定向到 API 文档
    @app.get("/", include_in_schema=False)
    async def root():
        """根路径重定向到 API 文档。"""
        return RedirectResponse(url="/docs")

    return app


async def _seed_config_tables(session) -> None:
    """种子默认平台配置、通知配置和绑定关系。"""
    from sqlalchemy import select
    from code_review.models.db import (
        PlatformConfig,
        NotificationConfig,
        PlatformNotificationBinding,
    )

    # 种子平台配置
    default_platforms = [
        {"platform": "gitee", "api_url": "https://gitee.com/api/v5", "description": "Gitee 代码平台"},
        {"platform": "github", "api_url": "https://api.github.com", "description": "GitHub 代码平台"},
        {"platform": "gitlab", "api_url": "https://gitlab.com/api/v4", "description": "GitLab 代码平台"},
    ]
    for p in default_platforms:
        existing = await session.execute(
            select(PlatformConfig).where(PlatformConfig.platform == p["platform"])
        )
        if existing.scalar_one_or_none() is None:
            session.add(PlatformConfig(enabled=True, **p))

    # 种子通知配置
    default_notifications = [
        {"channel": "dingtalk", "description": "钉钉机器人通知"},
        {"channel": "feishu", "description": "飞书机器人通知"},
    ]
    for n in default_notifications:
        existing = await session.execute(
            select(NotificationConfig).where(NotificationConfig.channel == n["channel"])
        )
        if existing.scalar_one_or_none() is None:
            session.add(NotificationConfig(enabled=False, **n))

    await session.commit()

    # 种子绑定关系
    platforms = (await session.execute(select(PlatformConfig))).scalars().all()
    notifications = (await session.execute(select(NotificationConfig))).scalars().all()
    for pc in platforms:
        for nc in notifications:
            existing = await session.execute(
                select(PlatformNotificationBinding).where(
                    PlatformNotificationBinding.platform_id == pc.id,
                    PlatformNotificationBinding.notification_id == nc.id,
                )
            )
            if existing.scalar_one_or_none() is None:
                session.add(PlatformNotificationBinding(
                    platform_id=pc.id,
                    notification_id=nc.id,
                    enabled=True,
                ))
    await session.commit()


# WSGI/ASGI 入口
app = create_app()
