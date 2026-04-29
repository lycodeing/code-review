"""评审规则引擎 — 对 diff 执行确定性规则检查。"""

import logging
import re
from fnmatch import fnmatch
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from code_review.core.llm import ReviewComment, Severity
from code_review.core.platform import FileChange
from code_review.models.db import ProjectRuleBinding, ReviewRule

logger = logging.getLogger(__name__)

# 规则执行超时（秒）
_PATTERN_TIMEOUT = 5


def _severity_from_str(s: str) -> Severity:
    """字符串转 Severity 枚举。"""
    mapping = {
        "critical": Severity.CRITICAL,
        "warning": Severity.WARNING,
        "suggestion": Severity.SUGGESTION,
        "info": Severity.INFO,
    }
    return mapping.get(s, Severity.WARNING)


async def get_rules_for_project(
    session: AsyncSession, project_id: UUID
) -> list[ReviewRule]:
    """获取项目绑定的所有启用规则。"""
    stmt = (
        select(ReviewRule)
        .join(ProjectRuleBinding)
        .where(
            ProjectRuleBinding.project_id == project_id,
            ProjectRuleBinding.enabled.is_(True),
            ReviewRule.enabled.is_(True),
        )
        .order_by(ReviewRule.name)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


def check_file_against_rules(
    file_change: FileChange,
    rules: list[ReviewRule],
) -> list[ReviewComment]:
    """对单个文件的 diff 执行规则检查。"""
    comments: list[ReviewComment] = []

    for rule in rules:
        # 文件模式匹配
        if rule.file_pattern and rule.file_pattern != "**":
            if not fnmatch(file_change.path, rule.file_pattern):
                continue

        if rule.rule_type != "regex":
            continue

        diff_text = file_change.diff or ""
        if not diff_text:
            continue

        try:
            # 编译正则并搜索
            compiled = re.compile(rule.pattern, re.MULTILINE)
            matches = list(compiled.finditer(diff_text))

            for match in matches:
                # 从 diff 行中估算行号（简易方式）
                line_no = _estimate_line_number(diff_text, match.start())
                comments.append(ReviewComment(
                    file_path=file_change.path,
                    line_start=line_no,
                    line_end=line_no,
                    severity=_severity_from_str(rule.severity),
                    message=rule.message,
                    suggestion=f"规则 [{rule.name}] 命中: `{match.group()}`",
                ))

        except re.error as e:
            logger.warning("规则 %s 正则编译失败: %s", rule.name, e)
        except Exception as e:
            logger.warning("规则 %s 执行失败: %s", rule.name, e)

    return comments


def check_changes_against_rules(
    changes: list[FileChange],
    rules: list[ReviewRule],
) -> list[ReviewComment]:
    """对所有变更文件执行规则检查。"""
    if not rules:
        return []

    all_comments: list[ReviewComment] = []
    for change in changes:
        comments = check_file_against_rules(change, rules)
        all_comments.extend(comments)

    if all_comments:
        logger.info("规则引擎命中 %d 条规则", len(all_comments))

    return all_comments


def _estimate_line_number(text: str, pos: int) -> int:
    """估算 diff 文本中某个位置的行号。"""
    line = 1
    for i in range(min(pos, len(text))):
        if text[i] == '\n':
            line += 1
    return line
