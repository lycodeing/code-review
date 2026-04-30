"""评审编排器 - 核心业务逻辑。

协调整个评审流程：接收事件 → 去重 → 获取变更 → 调用 LLM → 聚合评论 → 发布 → 通知。
"""

import logging
from dataclasses import replace
from fnmatch import fnmatch
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from code_review.adapters.factory import create_adapter
from code_review.core.llm import ReviewResult
from code_review.core.notification import NotificationPayload
from code_review.core.platform import (
    CommentPosition,
    FileChange,
    PublishComment,
    WebhookEvent,
)
from code_review.infrastructure.cache import event_dedup_cache
from code_review.infrastructure.celery_app import get_celery
from code_review.infrastructure.langchain_reviewer import LangChainReviewer
from code_review.infrastructure.notification_manager import NotificationManager
from code_review.infrastructure.prompt_manager import PromptTemplateManager
from code_review.models.config import AppConfig, LLMConfig
from code_review.models.db import Base, Project, ReviewTask, now_cst
from code_review.models.db import ReviewComment as ReviewCommentDB
from code_review.services.comment_aggregator import CommentAggregator
from code_review.services.llm_config_service import LLMConfigService
from code_review.services.platform_config_service import PlatformConfigService
from code_review.services.prompt_template_service import PromptTemplateService, seed_default_templates
from code_review.services.rule_engine import check_changes_against_rules, get_rules_for_project

logger = logging.getLogger(__name__)


class ReviewOrchestrator:
    """评审编排器。"""

    def __init__(
        self,
        config: AppConfig,
        session_factory: async_sessionmaker | None = None,
        secret_key: str = "",
    ):
        self._config = config
        self._secret_key = secret_key
        self._prompt_manager = PromptTemplateManager(language=config.review.comment_language)
        self._notification_manager = NotificationManager(config)
        self._aggregator = CommentAggregator(
            max_comments=config.review.max_comments_per_mr,
            summary_threshold=config.review.severity_threshold_for_summary,
            comment_mode=config.review.comment_mode,
        )
        # 数据库引擎（延迟初始化，避免跨事件循环问题）
        self._engine = None
        self._session_factory = session_factory

    def _ensure_engine(self):
        """确保引擎在当前事件循环中创建。"""
        if self._session_factory is not None:
            return  # 外部注入了 session_factory，无需自建引擎
        if self._engine is None:
            self._engine = create_async_engine(
                self._config.database.url, echo=self._config.database.echo,
                pool_size=self._config.database.pool_size,
            )
            self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    @property
    def session_factory(self):
        self._ensure_engine()
        return self._session_factory

    async def init_db(self) -> None:
        """创建数据库表并种子默认 Prompt 模板。"""
        self._ensure_engine()
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # 种子默认模板
        async with self._session_factory() as session:
            await seed_default_templates(session)

    async def _get_platform_config(self, platform: str):
        """获取平台配置（DB 优先，env 降级）。"""
        # 获取 env 降级值
        env_fallbacks = {
            "github": (self._config.github.token, self._config.github.api_url, self._config.github.webhook_secret),
            "gitlab": (self._config.gitlab.token, self._config.gitlab.api_url, self._config.gitlab.webhook_secret),
            "gitee": (self._config.gitee.token, self._config.gitee.api_url, self._config.gitee.webhook_secret),
        }
        env_token, env_api_url, env_secret = env_fallbacks.get(platform, ("", "", ""))

        async with self.session_factory() as session:
            svc = PlatformConfigService(session, self._secret_key)
            return await svc.get_by_platform_with_fallback(
                platform,
                env_token=env_token,
                env_api_url=env_api_url,
                env_webhook_secret=env_secret,
            )

    async def _init_notification_channels(self, platform: str = "") -> None:
        """初始化通知渠道（DB 优先，env 降级）。"""
        if self._session_factory and self._secret_key:
            await self._notification_manager.init_channels_from_db(
                self._session_factory, self._secret_key, platform=platform,
            )
        else:
            self._notification_manager.init_channels_sync()

    async def process_webhook_event(self, event: WebhookEvent) -> ReviewTask | None:
        """处理 Webhook 事件入口。

        1. 查找项目配置
        2. 查找或创建主记录（同一 PR 复用）
        3. 创建子版本记录（后续 push）
        4. 分发到 Celery 异步执行

        注意：去重检查已在 webhook 端点层完成，此处不再重复检查。
        """
        self._ensure_engine()
        # 去重缓存设置（由 webhook 端点调用前设置，这里确保设置）
        event_dedup_cache.set(event.event_id, True, ttl=3600)

        async with self._session_factory() as session:
            # 查找匹配的项目
            project = await self._find_project(session, event)
            if not project:
                logger.warning(
                    "No project found for %s/%s",
                    event.platform.value,
                    event.project_id,
                )
                return None

            # 检查是否为可触发评审的动作
            if event.action not in ("opened", "synchronize", "updated", "reopened"):
                logger.info("Action '%s' does not trigger review", event.action)
                return None

            # 分支过滤（基于 Project.config JSON 配置）
            project_config = project.config or {}
            if not self._should_review_branch(event, project_config):
                logger.info(
                    "分支 %s 被过滤，跳过评审（project=%s）",
                    event.source_branch, project.name,
                )
                return None

            # 检查 MR 标题或描述中是否包含跳过标记
            skip_markers = ["[skip-review]", "[no-review]"]
            mr_title = (event.mr_title or "").lower()
            mr_description = str(event.raw_payload.get("description") or event.raw_payload.get("body") or "").lower()
            if any(marker in mr_title or marker in mr_description for marker in skip_markers):
                logger.info(
                    "MR 包含跳过标记，跳过评审（project=%s, mr=%s, title=%s）",
                    project.name, event.mr_iid, event.mr_title,
                )
                return None

            # 查找该 PR 是否已有主记录（FOR UPDATE 防止并发创建重复主记录）
            existing = await session.execute(
                select(ReviewTask).where(
                    ReviewTask.project_id == project.id,
                    ReviewTask.mr_iid == event.mr_iid,
                    ReviewTask.parent_id.is_(None),
                ).with_for_update()
            )
            parent_task = existing.scalar_one_or_none()

            if parent_task:
                parent_task.is_latest = False
                parent_task.mr_title = event.mr_title or parent_task.mr_title
                parent_task.mr_author = event.mr_author or parent_task.mr_author
                parent_task.mr_url = event.mr_url or parent_task.mr_url
                parent_task.source_branch = event.source_branch or parent_task.source_branch
                parent_task.target_branch = event.target_branch or parent_task.target_branch

                # 批量清除所有旧子版本的 is_latest 标记
                await session.execute(
                    update(ReviewTask)
                    .where(ReviewTask.parent_id == parent_task.id, ReviewTask.is_latest.is_(True))
                    .values(is_latest=False)
                )

                # 取消所有未完成的旧版本（pending / in_progress）
                now_naive = now_cst().replace(tzinfo=None)
                cancel_result = await session.execute(
                    update(ReviewTask)
                    .where(
                        (ReviewTask.id == parent_task.id) | (ReviewTask.parent_id == parent_task.id),
                        ReviewTask.status.in_([ReviewTask.Status.PENDING, ReviewTask.Status.IN_PROGRESS]),
                    )
                    .values(
                        status=ReviewTask.Status.CANCELLED,
                        error_message="新评审已触发，自动取消",
                        completed_at=now_naive,
                    )
                )
                if cancel_result.rowcount:
                    logger.info(
                        "取消 %d 个未完成的旧版本（project=%s, mr=%s）",
                        cancel_result.rowcount, project.name, event.mr_iid,
                    )

                # 取主记录和所有子版本中最大的 revision，防止 revision 号重复
                max_rev = (await session.execute(
                    select(func.coalesce(func.max(ReviewTask.revision), 0))
                    .where(
                        (ReviewTask.id == parent_task.id) | (ReviewTask.parent_id == parent_task.id)
                    )
                )).scalar()
                new_revision = max_rev + 1

                task = ReviewTask(
                    project_id=project.id,
                    mr_iid=event.mr_iid,
                    event_id=event.event_id,
                    trigger_action=event.action,
                    mr_title=event.mr_title,
                    mr_author=event.mr_author,
                    mr_url=event.mr_url,
                    source_branch=event.source_branch,
                    target_branch=event.target_branch,
                    status=ReviewTask.Status.PENDING,
                    parent_id=parent_task.id,
                    revision=new_revision,
                    is_latest=True,
                )
            else:
                # 首次创建主记录
                task = ReviewTask(
                    project_id=project.id,
                    mr_iid=event.mr_iid,
                    event_id=event.event_id,
                    trigger_action=event.action,
                    mr_title=event.mr_title,
                    mr_author=event.mr_author,
                    mr_url=event.mr_url,
                    source_branch=event.source_branch,
                    target_branch=event.target_branch,
                    status=ReviewTask.Status.PENDING,
                    parent_id=None,
                    revision=1,
                    is_latest=True,
                )

            session.add(task)
            await session.commit()
            await session.refresh(task)

        # 分发 Celery 任务
        try:
            celery = get_celery()
            celery_result = celery.send_task(
                "code_review.execute_review",
                args=[str(task.id)],
                queue="review",
            )
            # 更新 celery_task_id
            async with self._session_factory() as session:
                db_task = await session.get(ReviewTask, task.id)
                if db_task:
                    db_task.celery_task_id = celery_result.id
                    await session.commit()
        except Exception as e:
            logger.error("Failed to dispatch Celery task: %s", e)
            # 降级为同步执行
            await self.execute_review(str(task.id))

        return task

    async def execute_review(self, task_id: str) -> None:
        """执行完整的评审流程。"""
        self._ensure_engine()
        async with self._session_factory() as session:
            task = await session.get(ReviewTask, UUID(task_id))
            if not task:
                logger.error("Review task not found: %s", task_id)
                return

            try:
                # 执行前检查任务是否已被取消（新评审到来时会取消旧版本）
                if task.status == ReviewTask.Status.CANCELLED:
                    logger.info("任务已被取消，跳过执行: %s", task_id)
                    return

                # 更新状态为评审中
                task.status = ReviewTask.Status.IN_PROGRESS
                task.started_at = now_cst()
                await session.commit()

                # 获取项目配置
                project = await session.get(Project, task.project_id)
                if not project:
                    raise ValueError(f"Project not found: {task.project_id}")

                # 从 DB 获取平台配置（env 降级）
                platform_config = await self._get_platform_config(project.platform)
                if not platform_config:
                    raise ValueError(f"No platform config for: {project.platform}")

                # 创建平台适配器
                adapter = create_adapter(
                    platform=project.platform,
                    platform_config=platform_config,
                    project_webhook_secret=project.webhook_secret or "",
                )

                # 获取 MR 信息
                mr_info = await adapter.get_mr_info(
                    project.platform_project_id, task.mr_iid
                )
                task.mr_title = mr_info.title
                task.mr_author = mr_info.author
                task.mr_url = mr_info.web_url or mr_info.url
                task.source_branch = mr_info.source_branch
                task.target_branch = mr_info.target_branch

                # 获取变更文件列表
                changes = await adapter.get_mr_changes(
                    project.platform_project_id, task.mr_iid
                )

                # 文件过滤
                filtered_changes = self._filter_files(
                    changes, project.config or {}
                )

                if not filtered_changes:
                    task.status = ReviewTask.Status.COMPLETED
                    task.summary = "No reviewable files found after filtering."
                    task.completed_at = now_cst()
                    await session.commit()
                    return

                # 合并 diff
                combined_diff = self._combine_diffs(filtered_changes)

                # 上下文增强：加载 diff 中引用的相关文件
                related_context: dict[str, str] = {}
                ctx_enabled = await settings_svc.get_bool("context_enhancement_enabled", True)
                if ctx_enabled:
                    from code_review.services.context_extractor import ContextExtractor
                    ctx_extractor = ContextExtractor()
                    max_ctx_files = await settings_svc.get_int("context_max_files", 5)
                    max_ctx_size = await settings_svc.get_int("context_max_file_size", 10000)
                    related_context = await ctx_extractor.extract_context(
                        adapter=adapter,
                        project_id=project.platform_project_id,
                        changes=filtered_changes,
                        source_branch=task.source_branch or "main",
                        max_files=max_ctx_files,
                        max_file_size=max_ctx_size,
                    )

                # 执行规则引擎（确定性检查，在 LLM 评审前执行）
                rules = await get_rules_for_project(session, task.project_id)
                rule_comments = check_changes_against_rules(filtered_changes, rules)

                # 选择 prompt 模板（从数据库动态加载，支持热更新）
                languages = {
                    self._prompt_manager.detect_language(c.path)
                    for c in filtered_changes
                }
                # 使用最主要的语言模板（或 default）
                main_language = max(languages, key=lambda l: sum(
                    1 for c in filtered_changes
                    if self._prompt_manager.detect_language(c.path) == l
                )) if languages else "default"

                # 优先级：项目绑定模板 > 项目 config 指定名称 > 按分类自动匹配
                prompt = None
                prompt_svc = PromptTemplateService(session)
                # 1. 尝试从项目绑定获取模板
                bound_tpl = await prompt_svc.get_template_for_project(task.project_id)
                if bound_tpl:
                    logger.info(f"使用项目绑定的模板: {bound_tpl.name}")
                    prompt = bound_tpl.content
                else:
                    # 2. 尝试从项目 config 中指定的模板名称
                    project_template_name = (
                        (project.config or {}).get("prompt_template_name")
                    )
                    # 3. 按分类自动匹配
                    prompt = await self._prompt_manager.get_template(
                        session=session,
                        language=main_language,
                        template_name=project_template_name,
                    )

                # 获取项目的 LLM 配置链（按优先级排序，用于故障转移）
                llm_config_service = LLMConfigService(session, self._secret_key)
                llm_config_chain = await llm_config_service.get_llm_configs_chain(task.project_id)

                logger.debug("项目 %s 的 LLM 配置链: %s", task.project_id, [c.name for c in llm_config_chain])

                # 从系统配置获取 LLM 超时时间
                from code_review.services.system_settings_service import SystemSettingsService
                settings_svc = SystemSettingsService(session)
                llm_timeout = await settings_svc.get_int("llm_timeout_seconds", 120)
                llm_timeout_value = None if llm_timeout == -1 else llm_timeout

                # 构造 LLM 配置候选列表
                llm_candidates: list[tuple[str, LLMConfig]] = []
                for llm_config in llm_config_chain:
                    api_key = await llm_config_service.decrypt_api_key(llm_config.api_key)
                    llm_settings = LLMConfig(
                        model=llm_config.model_name,
                        api_key=api_key,
                        api_base=llm_config.api_base or "",
                        temperature=llm_config.extra_params.get("temperature", 0.3) if llm_config.extra_params else 0.3,
                        max_tokens=llm_config.extra_params.get("max_tokens", 4096) if llm_config.extra_params else 4096,
                        timeout=llm_config.extra_params.get("timeout", llm_timeout_value) if llm_config.extra_params else llm_timeout_value,
                        response_format=llm_config.response_format or "auto",
                        extra_params=llm_config.extra_params,
                    )
                    llm_candidates.append((llm_config.name, llm_settings))

                # 无数据库配置时，降级到环境变量
                if not llm_candidates:
                    env_llm = self._config.llm
                    env_llm.timeout = llm_timeout_value if llm_timeout_value is not None else env_llm.timeout
                    llm_candidates.append(("env_default", env_llm))
                    logger.info("无数据库 LLM 配置，降级到环境变量, model=%r", self._config.llm.model)

                # 按优先级尝试 LLM 调用，失败则自动降级到下一个
                result: ReviewResult | None = None
                last_error: Exception | None = None
                tried_configs: list[str] = []

                for config_name, llm_settings in llm_candidates:
                    try:
                        logger.info("尝试 LLM 配置: %s, model=%s", config_name, llm_settings.model)
                        reviewer = LangChainReviewer(llm_settings)
                        result = await reviewer.review(
                            diff=combined_diff,
                            files=filtered_changes,
                            prompt_template=prompt,
                            task_id=task.id,
                            session_factory=self._session_factory,
                            related_context=related_context if related_context else None,
                            project_id=task.project_id,
                        )
                        task.model_name = result.model
                        logger.info("LLM 配置 %s 评审成功, model=%s", config_name, result.model)
                        break
                    except Exception as e:
                        tried_configs.append(config_name)
                        last_error = e
                        logger.warning(
                            "LLM 配置 %s (model=%s) 调用失败: %s",
                            config_name, llm_settings.model, e,
                        )
                        if len(llm_candidates) > 1:
                            logger.info("尝试故障转移到下一个 LLM 配置...")
                        continue

                if result is None:
                    raise RuntimeError(
                        f"所有 LLM 配置均失败（已尝试: {', '.join(tried_configs)}）: {last_error}"
                    )

                # LLM 调用完成后再次检查是否被取消（LLM 调用耗时最长，期间可能有新评审到来）
                await session.refresh(task)
                if task.status == ReviewTask.Status.CANCELLED:
                    logger.info("任务在 LLM 调用期间被取消，跳过后续处理: %s", task_id)
                    return

                # 合并规则引擎评论和 LLM 评论
                if rule_comments:
                    logger.info("规则引擎命中 %d 条，LLM 评论 %d 条", len(rule_comments), len(result.comments))
                    result.comments.extend(rule_comments)

                # 聚合评论
                aggregated, summary = self._aggregator.aggregate(result.comments)
                task.summary = summary or result.summary
                task.total_comments = len(result.comments)
                task.critical_count = sum(
                    1 for c in result.comments if c.severity.value == "critical"
                )
                task.warning_count = sum(
                    1 for c in result.comments if c.severity.value == "warning"
                )

                # 发布评论到平台
                publish_comments = self._to_publish_comments(aggregated)
                if publish_comments:
                    await adapter.publish_comments_batch(
                        project.platform_project_id,
                        task.mr_iid,
                        publish_comments,
                    )

                # 生成并发布 PR 摘要
                pr_desc_enabled = await settings_svc.get_bool("pr_description_enabled", True)
                if pr_desc_enabled and task.summary:
                    pr_desc_mode = await settings_svc.get_string("pr_description_mode", "full")
                    pr_description = self._build_pr_description(
                        task, result.comments, filtered_changes, mode=pr_desc_mode,
                    )
                    try:
                        await adapter.publish_comment(
                            project.platform_project_id,
                            task.mr_iid,
                            PublishComment(body=pr_description, position=None),
                        )
                        task.pr_description = pr_description
                        task.description_posted = True
                        logger.info("PR 摘要已发布: task=%s", task_id)
                    except Exception as e:
                        logger.warning("PR 摘要发布失败（不影响评审结果）: %s", e)

                # 保存评审意见到数据库
                for comment in result.comments:
                    db_comment = ReviewCommentDB(
                        task_id=task.id,
                        file_path=comment.file_path,
                        line_start=comment.line_start,
                        line_end=comment.line_end,
                        severity=comment.severity.value,
                        message=comment.message,
                        suggestion=comment.suggestion,
                    )
                    session.add(db_comment)

                # 发送通知（使用平台绑定的通知渠道）
                await self._init_notification_channels(platform=project.platform)
                notification_payload = NotificationPayload(
                    mr_title=mr_info.title,
                    mr_author=mr_info.author,
                    mr_url=mr_info.web_url or mr_info.url,
                    project_name=project.name,
                    summary=task.summary or "",
                    critical_count=task.critical_count or 0,
                    warning_count=task.warning_count or 0,
                    suggestion_count=sum(
                        1 for c in result.comments
                        if c.severity.value == "suggestion"
                    ),
                    info_count=sum(
                        1 for c in result.comments
                        if c.severity.value == "info"
                    ),
                    detail_link=mr_info.web_url or mr_info.url,
                )
                await self._notification_manager.notify_all(
                    notification_payload,
                    project_id=task.project_id,
                    task_id=task.id,
                    session_factory=self._session_factory,
                    project_config=project.config,
                )

                task.status = ReviewTask.Status.COMPLETED
                task.completed_at = now_cst()
                await session.commit()

                logger.info(
                    "Review completed: task=%s, comments=%d",
                    task_id, len(result.comments),
                )

            except Exception as e:
                logger.error("Review failed for task %s: %s", task_id, e, exc_info=True)
                task.status = ReviewTask.Status.FAILED
                task.error_message = str(e)
                task.completed_at = now_cst()
                await session.commit()

    async def _find_project(
        self, session: AsyncSession, event: WebhookEvent
    ) -> Project | None:
        """根据事件查找匹配的项目配置。"""
        logger.debug(
            "查找项目: platform=%s, project_id=%r",
            event.platform.value,
            event.project_id,
        )
        stmt = select(Project).where(
            Project.platform == event.platform.value,
            Project.platform_project_id == event.project_id,
            Project.enabled == 1,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    def _filter_files(
        self, changes: list[FileChange], project_config: dict
    ) -> list[FileChange]:
        """根据排除规则和 diff 大小限制过滤文件。"""
        # 项目级配置覆盖全局配置
        exclude_patterns = project_config.get(
            "exclude_patterns", self._config.review.exclude_patterns
        )
        # diff 大小限制（字符数，超过则截断部分文件）
        max_diff_size = project_config.get("max_diff_size", 0)

        filtered = []
        for change in changes:
            excluded = any(
                fnmatch(change.path, pattern) for pattern in exclude_patterns
            )
            if not excluded:
                filtered.append(change)

        # 过滤包含行级跳过标记的 diff 行（# noqa: ai-review 或 // noqa: ai-review）
        noqa_markers = ("# noqa: ai-review", "// noqa: ai-review")
        cleaned = []
        for change in filtered:
            if change.diff and any(m in change.diff for m in noqa_markers):
                clean_diff = "".join(
                    line for line in change.diff.splitlines(keepends=True)
                    if not any(m in line for m in noqa_markers)
                )
                change = replace(change, diff=clean_diff)
            cleaned.append(change)
        filtered = cleaned

        # 按 max_diff_size 裁剪（保留前面的文件，通常是按重要性排序）
        if max_diff_size > 0:
            total = 0
            trimmed = []
            for change in filtered:
                diff_len = len(change.diff) if change.diff else 0
                if total + diff_len > max_diff_size:
                    logger.info(
                        "diff 超过 max_diff_size=%d，截断剩余文件（已包含 %d 个文件）",
                        max_diff_size, len(trimmed),
                    )
                    break
                total += diff_len
                trimmed.append(change)
            filtered = trimmed

        return filtered

    @staticmethod
    def _should_review_branch(event: WebhookEvent, project_config: dict) -> bool:
        """检查分支是否应该触发评审。

        配置格式（在 Project.config JSON 中）：
        {
            "include_branches": ["main", "develop", "release/*"],  // 白名单，空则全部允许
            "exclude_branches": ["experimental/*", "test/*"]       // 黑名单
        }
        """
        source_branch = event.source_branch
        if not source_branch:
            return True

        include_branches = project_config.get("include_branches", [])
        exclude_branches = project_config.get("exclude_branches", [])

        # 白名单检查：配置了白名单时，必须匹配至少一条规则
        if include_branches:
            included = any(fnmatch(source_branch, p) for p in include_branches)
            if not included:
                return False

        # 黑名单检查：匹配任何一条规则则排除
        if exclude_branches:
            excluded = any(fnmatch(source_branch, p) for p in exclude_branches)
            if excluded:
                return False

        return True

    @staticmethod
    def _combine_diffs(changes: list[FileChange]) -> str:
        """合并多个文件的 diff 为单个文本。"""
        parts = []
        for change in changes:
            if change.diff:
                header = f"diff --git a/{change.path} b/{change.path}"
                parts.append(header)
                parts.append(change.diff)
        return "\n".join(parts)

    @staticmethod
    def _build_pr_description(
        task: ReviewTask,
        comments: list,
        changes: list,
        mode: str = "full",
    ) -> str:
        """用评审结果组装 PR 摘要（不调用 LLM）。"""
        from collections import Counter

        body = "## AI 评审摘要\n\n"
        body += f"**{task.summary}**\n\n"

        if mode == "full":
            severity_counts = Counter(
                c.severity.value if hasattr(c.severity, 'value') else c.severity
                for c in comments
            )
            body += "| 级别 | 数量 |\n|------|------|\n"
            for sev in ("critical", "warning", "suggestion", "info"):
                count = severity_counts.get(sev, 0)
                if count > 0:
                    body += f"| {sev} | {count} |\n"

            file_list = sorted({
                c.file_path for c in comments if hasattr(c, 'file_path') and c.file_path
            })
            if file_list:
                body += "\n**涉及文件：**\n"
                for f in file_list[:10]:
                    body += f"- `{f}`\n"

        return body

    @staticmethod
    def _to_publish_comments(
        aggregated: list,
    ) -> list[PublishComment]:
        """将聚合后的评论转换为平台发布格式。"""
        comments = []
        for agg in aggregated:
            position = CommentPosition(
                path=agg.file_path,
                line=agg.line_start,
            )
            comments.append(PublishComment(
                body=agg.body,
                position=position,
                severity=agg.severity.value if hasattr(agg.severity, "value") else str(agg.severity),
            ))
        return comments

    async def close(self) -> None:
        """清理资源。"""
        if self._engine:
            await self._engine.dispose()
