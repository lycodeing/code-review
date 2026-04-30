"""FastAPI 应用入口。"""

import asyncio
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
from code_review.api.review_rules import router as review_rules_router
from code_review.api.comment_replies import router as comment_replies_router
from code_review.api.comments import router as comments_router
from code_review.api.system_settings import router as system_settings_router
from code_review.infrastructure.celery_app import init_celery
from code_review.infrastructure.notification_manager import NotificationManager
from code_review.models.config import AppConfig
from code_review.models.db import Base, ReviewTask, now_cst
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

        # 启动超时检查后台任务
        stop_event = asyncio.Event()
        asyncio.create_task(
            _timeout_check_loop(session_factory, stop_event)
        )

        yield

        # 清理
        stop_event.set()
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
    app.include_router(review_rules_router)
    app.include_router(comment_replies_router)
    app.include_router(comments_router)
    app.include_router(system_settings_router)

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

    # 种子系统配置（超时等通用 key-value）
    from code_review.models.db import SystemSetting

    default_settings = [
        {
            "key": "review_timeout_seconds", "value": "1800",
            "value_type": "int", "input_type": "number",
            "category": "timeout",
            "label": "评审超时时间",
            "description": "评审任务的超时时间（秒），超时后自动标记为 TIMEOUT 状态。-1 表示无限制",
            "unit": "秒", "default_value": "1800",
            "sort_order": 1,
        },
        {
            "key": "llm_timeout_seconds", "value": "120",
            "value_type": "int", "input_type": "number",
            "category": "timeout",
            "label": "AI 请求超时时间",
            "description": "调用大模型的请求超时时间（秒）。-1 表示无限制",
            "unit": "秒", "default_value": "120",
            "sort_order": 2,
        },
        {
            "key": "notification_timeout_seconds", "value": "30",
            "value_type": "int", "input_type": "number",
            "category": "timeout",
            "label": "通知发送超时时间",
            "description": "发送通知（飞书/钉钉）的 HTTP 请求超时时间（秒）。-1 表示无限制",
            "unit": "秒", "default_value": "30",
            "sort_order": 3,
        },
    ]
    for s in default_settings:
        existing = await session.execute(
            select(SystemSetting).where(SystemSetting.key == s["key"])
        )
        if existing.scalar_one_or_none() is None:
            session.add(SystemSetting(**s))
    await session.commit()


# WSGI/ASGI 入口
app = create_app()


async def _timeout_check_loop(session_factory, stop_event: asyncio.Event) -> None:
    """后台定时检查评审任务超时。"""
    from datetime import datetime, timedelta
    from sqlalchemy import select
    from code_review.services.system_settings_service import SystemSettingsService

    logger.info("评审超时检查任务已启动")
    while not stop_event.is_set():
        try:
            async with session_factory() as session:
                svc = SystemSettingsService(session)
                timeout_seconds = await svc.get_int("review_timeout_seconds", 1800)

                # -1 表示无限制，跳过检查
                if timeout_seconds == -1:
                    pass
                else:
                    # 数据库列为 timestamp without time zone，使用 naive datetime 比较
                    now = now_cst().replace(tzinfo=None)
                    cutoff = now - timedelta(seconds=timeout_seconds)
                    stmt = select(ReviewTask).where(
                        ReviewTask.status == ReviewTask.Status.IN_PROGRESS,
                        ReviewTask.started_at.isnot(None),
                        ReviewTask.started_at < cutoff,
                    )
                    result = await session.execute(stmt)
                    timed_out = result.scalars().all()
                    for task in timed_out:
                        task.status = ReviewTask.Status.TIMEOUT
                        task.error_message = f"评审超时（超过 {timeout_seconds} 秒）"
                        task.completed_at = now
                        logger.warning("评审任务超时: %s, started_at=%s", task.id, task.started_at)
                    if timed_out:
                        await session.commit()
                        logger.info("标记 %d 个评审任务为超时", len(timed_out))
        except Exception as e:
            logger.error("超时检查失败: %s", e)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=120)
        except asyncio.TimeoutError:
            pass
