"""评论聚合器测试。"""

from code_review.core.llm import ReviewComment, Severity
from code_review.services.comment_aggregator import CommentAggregator


def _make_comment(
    file_path: str = "src/main.py",
    line_start: int = 1,
    line_end: int = 1,
    severity: Severity = Severity.WARNING,
    message: str = "test",
    suggestion: str = "",
) -> ReviewComment:
    return ReviewComment(
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        severity=severity,
        message=message,
        suggestion=suggestion,
    )


class TestCommentAggregator:
    """评论聚合器核心逻辑测试。"""

    def test_empty_comments(self):
        agg = CommentAggregator()
        result, summary = agg.aggregate([])
        assert result == []
        assert summary == ""

    def test_single_comment(self):
        agg = CommentAggregator()
        comments = [_make_comment(message="issue found")]
        result, summary = agg.aggregate(comments)
        assert len(result) == 1
        assert result[0].file_path == "src/main.py"
        assert "issue found" in result[0].messages

    def test_merge_adjacent_same_file(self):
        """相邻行 + 同 severity 应合并。"""
        agg = CommentAggregator()
        comments = [
            _make_comment(line_start=10, line_end=12, severity=Severity.WARNING, message="A"),
            _make_comment(line_start=14, line_end=16, severity=Severity.WARNING, message="B"),
        ]
        result, _ = agg.aggregate(comments)
        assert len(result) == 1  # 合并为 1 条
        assert result[0].line_start == 10
        assert result[0].line_end == 16
        assert "A" in result[0].messages
        assert "B" in result[0].messages

    def test_no_merge_different_severity(self):
        """不同 severity 不合并。"""
        agg = CommentAggregator()
        comments = [
            _make_comment(line_start=10, severity=Severity.CRITICAL, message="A"),
            _make_comment(line_start=12, severity=Severity.WARNING, message="B"),
        ]
        result, _ = agg.aggregate(comments)
        assert len(result) == 2

    def test_no_merge_far_apart_lines(self):
        """行号相距过远不合并。"""
        agg = CommentAggregator()
        comments = [
            _make_comment(line_start=10, severity=Severity.WARNING, message="A"),
            _make_comment(line_start=50, severity=Severity.WARNING, message="B"),
        ]
        result, _ = agg.aggregate(comments)
        assert len(result) == 2

    def test_different_files_not_merged(self):
        """不同文件的评论不合并。"""
        agg = CommentAggregator()
        comments = [
            _make_comment(file_path="a.py", line_start=10, message="A"),
            _make_comment(file_path="b.py", line_start=10, message="B"),
        ]
        result, _ = agg.aggregate(comments)
        assert len(result) == 2

    def test_max_comments_truncation(self):
        """超过最大评论数时截断。"""
        agg = CommentAggregator(max_comments=3)
        comments = [
            _make_comment(line_start=i, severity=Severity.SUGGESTION, message=f"msg{i}")
            for i in range(10)
        ]
        result, _ = agg.aggregate(comments)
        assert len(result) <= 3

    def test_severity_priority_truncation(self):
        """截断时优先保留严重程度高的评论。"""
        agg = CommentAggregator(max_comments=2)
        comments = [
            _make_comment(line_start=1, severity=Severity.INFO, message="info"),
            _make_comment(line_start=2, severity=Severity.CRITICAL, message="critical"),
            _make_comment(line_start=3, severity=Severity.WARNING, message="warning"),
        ]
        result, _ = agg.aggregate(comments)
        severities = [c.severity for c in result]
        assert Severity.CRITICAL in severities
        assert Severity.WARNING in severities

    def test_summary_mode(self):
        """评论数超过阈值且配置 summary 模式时，不发布行内评论。"""
        agg = CommentAggregator(summary_threshold=5, comment_mode="summary")
        comments = [
            _make_comment(line_start=i, message=f"msg{i}")
            for i in range(10)
        ]
        result, summary = agg.aggregate(comments)
        assert result == []  # 不发布行内评论
        assert "10" in summary  # 摘要包含总数

    def test_summary_contains_severity_counts(self):
        agg = CommentAggregator()
        comments = [
            _make_comment(severity=Severity.CRITICAL, message="c"),
            _make_comment(severity=Severity.WARNING, message="w"),
            _make_comment(severity=Severity.SUGGESTION, message="s"),
            _make_comment(severity=Severity.INFO, message="i"),
        ]
        _, summary = agg.aggregate(comments)
        assert "严重" in summary or "Critical" in summary
