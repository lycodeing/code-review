"""评论聚合策略。

将同一文件相邻行号的评审意见合并，按严重程度分级，
并在评论数超过阈值时切换为摘要模式。
"""

import logging
from dataclasses import dataclass

from code_review.core.llm import ReviewComment, Severity

logger = logging.getLogger(__name__)

# 相邻行的判定距离阈值
ADJACENT_LINE_THRESHOLD = 5

# 严重程度排序权重
SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.WARNING: 1,
    Severity.SUGGESTION: 2,
    Severity.INFO: 3,
}


@dataclass
class AggregatedComment:
    """聚合后的评论。"""
    file_path: str
    line_start: int
    line_end: int
    severity: Severity
    messages: list[str]
    suggestions: list[str]

    @property
    def body(self) -> str:
        """格式化单条聚合评论，消息列表 + 代码建议块。"""
        parts = []
        for m in self.messages:
            parts.append(f"- {m}")
        if self.suggestions:
            parts.append("")
            parts.append("**💡 建议修复：**")
            parts.append("")
            for s in self.suggestions:
                # 如果建议包含行内代码（多词反号包裹），尝试提取为代码块
                formatted = self._format_suggestion(s)
                parts.append(formatted)
        return "\n".join(parts)

    @staticmethod
    def _format_suggestion(text: str) -> str:
        """将建议文本中的行内代码片段转为独立代码块。"""
        import re
        # 匹配包含 . 或 ( 或 { 或 ; 的行内代码 — 很可能是真实代码片段
        code_pattern = re.compile(r"`([^`]+[.;{}()\[\]][^`]*)`")
        match = code_pattern.search(text)
        if match:
            code_snippet = match.group(1)
            prose = text.replace(f"`{code_snippet}`", "").strip().rstrip("，。、：").strip()
            lines = []
            if prose:
                lines.append(f"{prose}：")
            lines.append("```java")
            lines.append(code_snippet)
            lines.append("```")
            return "\n".join(lines)
        return f"- {text}"


class CommentAggregator:
    """评论聚合器。"""

    def __init__(
        self,
        max_comments: int = 50,
        summary_threshold: int = 30,
        comment_mode: str = "detailed",
    ):
        self._max_comments = max_comments
        self._summary_threshold = summary_threshold
        self._comment_mode = comment_mode

    def aggregate(
        self, comments: list[ReviewComment]
    ) -> tuple[list[AggregatedComment], str]:
        """聚合评审意见。

        Returns:
            (聚合后的评论列表, 摘要文本)
        """
        if not comments:
            return [], ""

        # 按文件和起始行号排序
        sorted_comments = sorted(
            comments, key=lambda c: (c.file_path, c.line_start)
        )

        # 统计各严重程度数量
        severity_counts = self._count_severities(comments)

        # 如果评论数超过阈值且配置了摘要模式，生成摘要
        if (
            len(comments) > self._summary_threshold
            and self._comment_mode == "summary"
        ):
            summary = self._build_summary(comments, severity_counts)
            return [], summary

        # 按文件分组
        file_groups: dict[str, list[ReviewComment]] = {}
        for c in sorted_comments:
            file_groups.setdefault(c.file_path, []).append(c)

        # 同文件内聚合相邻行
        aggregated: list[AggregatedComment] = []
        for file_path, file_comments in file_groups.items():
            merged = self._merge_adjacent(file_comments)
            aggregated.extend(merged)

        # 限制最大评论数
        if len(aggregated) > self._max_comments:
            logger.warning(
                "Comments (%d) exceed max (%d), truncating by severity",
                len(aggregated),
                self._max_comments,
            )
            # 按严重程度排序，保留最严重的
            aggregated.sort(key=lambda c: SEVERITY_ORDER.get(c.severity, 99))
            aggregated = aggregated[: self._max_comments]

        summary = self._build_summary(comments, severity_counts)
        return aggregated, summary

    def _merge_adjacent(
        self, comments: list[ReviewComment]
    ) -> list[AggregatedComment]:
        """合并同一文件中相邻行的评论。"""
        if not comments:
            return []

        result: list[AggregatedComment] = []
        current = AggregatedComment(
            file_path=comments[0].file_path,
            line_start=comments[0].line_start,
            line_end=comments[0].line_end,
            severity=comments[0].severity,
            messages=[comments[0].message],
            suggestions=[comments[0].suggestion] if comments[0].suggestion else [],
        )

        for comment in comments[1:]:
            # 判断是否相邻
            if (
                comment.line_start - current.line_end <= ADJACENT_LINE_THRESHOLD
                and comment.severity == current.severity
            ):
                # 合并
                current.line_end = max(current.line_end, comment.line_end)
                current.messages.append(comment.message)
                if comment.suggestion:
                    current.suggestions.append(comment.suggestion)
            else:
                result.append(current)
                current = AggregatedComment(
                    file_path=comment.file_path,
                    line_start=comment.line_start,
                    line_end=comment.line_end,
                    severity=comment.severity,
                    messages=[comment.message],
                    suggestions=[comment.suggestion] if comment.suggestion else [],
                )

        result.append(current)
        return result

    @staticmethod
    def _count_severities(comments: list[ReviewComment]) -> dict[str, int]:
        counts: dict[str, int] = {
            "critical": 0, "warning": 0, "suggestion": 0, "info": 0,
        }
        for c in comments:
            key = c.severity.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _build_summary(
        self,
        comments: list[ReviewComment],
        severity_counts: dict[str, int],
    ) -> str:
        """构建评审摘要文本。"""
        lines = [
            f"**共 {len(comments)} 条评审意见：**\n",
            f"| 级别 | 数量 |",
            f"|------|------|",
            f"| 🔴 严重（Critical） | {severity_counts.get('critical', 0)} |",
            f"| 🟡 警告（Warning） | {severity_counts.get('warning', 0)} |",
            f"| 🔵 建议（Suggestion） | {severity_counts.get('suggestion', 0)} |",
            f"| ℹ️ 信息（Info） | {severity_counts.get('info', 0)} |",
        ]

        # 列出所有严重问题
        criticals = [c for c in comments if c.severity == Severity.CRITICAL]
        if criticals:
            lines.append("\n**🔴 严重问题：**\n")
            for c in criticals[:10]:
                lines.append(f"- `{c.file_path}:{c.line_start}` — {c.message}")

        return "\n".join(lines)
