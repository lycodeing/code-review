"""命令处理器 — 执行不同类型的评审命令。"""

import logging
from uuid import UUID

from code_review.services.command_router import CommandRouter
from code_review.services.rule_engine import get_rules_for_project, check_changes_against_rules
from code_review.core.platform import PublishComment

logger = logging.getLogger(__name__)


class CommandHandler:
    """命令处理器，负责执行不同类型的评审命令。"""

    def __init__(self, orchestrator):
        """初始化命令处理器。

        Args:
            orchestrator: ReviewOrchestrator 实例
        """
        self._orchestrator = orchestrator

    async def handle_review(self, event, session_factory) -> None:
        """处理 review 命令 - 触发完整评审。

        Args:
            event: WebhookEvent 实例
            session_factory: 数据库 session 工厂
        """
        await self._orchestrator.process_webhook_event(event)

    async def handle_describe(self, event, session_factory, adapter=None) -> None:
        """处理 describe 命令 - 生成 PR 描述。

        Args:
            event: WebhookEvent 实例
            session_factory: 数据库 session 工厂
            adapter: 平台适配器实例
        """
        raw = event.raw_payload
        project_id = raw.get("project_id", "")
        mr_iid = raw.get("mr_iid", "")

        if not adapter or not project_id or not mr_iid:
            logger.warning("describe 命令缺少必要参数")
            return

        try:
            changes = await adapter.get_mr_changes(project_id, mr_iid)
            mr_info = await adapter.get_mr_info(project_id, mr_iid)

            # 限制文件列表长度
            file_list = sorted({c.path for c in changes})[:10]

            body = f"## PR 描述\n\n"
            body += f"**标题:** {mr_info.title}\n"
            body += f"**作者:** {mr_info.author}\n"
            body += f"**分支:** {mr_info.source_branch} → {mr_info.target_branch}\n\n"
            body += f"**变更文件（{len(changes)} 个）：**\n"
            for f in file_list:
                body += f"- `{f}`\n"

            await adapter.publish_comment(
                project_id, mr_iid, PublishComment(body=body, position=None)
            )
            logger.info("describe 命令执行成功: project_id=%s, mr_iid=%s", project_id, mr_iid)
        except Exception as e:
            logger.error("describe 命令执行失败: %s", e, exc_info=True)

    async def handle_improve(self, event, session_factory) -> None:
        """处理 improve 命令 - 使用改进模板触发评审。

        Args:
            event: WebhookEvent 实例
            session_factory: 数据库 session 工厂
        """
        raw = event.raw_payload
        raw["force_template"] = "improve_zh"
        await self._orchestrator.process_webhook_event(event)

    async def handle_analyze(self, event, session_factory, adapter=None) -> None:
        """处理 analyze 命令 - 仅执行规则引擎检查。

        Args:
            event: WebhookEvent 实例
            session_factory: 数据库 session 工厂
            adapter: 平台适配器实例
        """
        raw = event.raw_payload
        project_id = raw.get("project_id", "")
        mr_iid = raw.get("mr_iid", "")
        db_project_id = raw.get("db_project_id")

        if not adapter or not db_project_id or not mr_iid:
            logger.warning("analyze 命令缺少必要参数")
            return

        try:
            changes = await adapter.get_mr_changes(project_id, mr_iid)

            async with session_factory() as session:
                rules = await get_rules_for_project(session, UUID(db_project_id))
                rule_comments = check_changes_against_rules(changes, rules)

            if rule_comments:
                body = "## 规则引擎检查结果\n\n"
                for rc in rule_comments:
                    sev = rc.severity.value if hasattr(rc.severity, 'value') else rc.severity
                    body += f"- **[{sev}]** `{rc.file_path}:{rc.line_start}` — {rc.message}\n"
                await adapter.publish_comment(
                    project_id, mr_iid, PublishComment(body=body, position=None)
                )
            else:
                await adapter.publish_comment(
                    project_id, mr_iid,
                    PublishComment(body="## 规则引擎检查结果\n\n未发现规则命中。", position=None)
                )
            logger.info("analyze 命令执行成功: project_id=%s, mr_iid=%s", project_id, mr_iid)
        except Exception as e:
            logger.error("analyze 命令执行失败: %s", e, exc_info=True)
