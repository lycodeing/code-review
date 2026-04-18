"""LLM 评审器测试。"""

import json

import pytest

from code_review.core.llm import Severity
from code_review.core.platform import FileChange
from code_review.infrastructure.llm_reviewer import LiteLLMReviewer
from code_review.infrastructure.response_parser import MultiFormatResponseParser
from code_review.models.config import LLMConfig


class TestLiteLLMReviewer:
    """LLM 评审器解析逻辑测试。"""

    def _make_reviewer(self) -> LiteLLMReviewer:
        config = LLMConfig(model="gpt-4", api_key="test-key")
        return LiteLLMReviewer(config)

    def test_parse_response_valid_json(self):
        """测试解析有效的 JSON 响应。"""
        parser = MultiFormatResponseParser()
        content = json.dumps({
            "summary": "Found 2 issues",
            "comments": [
                {
                    "file_path": "main.py",
                    "line_start": 10,
                    "line_end": 15,
                    "severity": "warning",
                    "message": "Unused variable",
                    "suggestion": "Remove the variable",
                },
                {
                    "file_path": "utils.py",
                    "line_start": 5,
                    "line_end": 5,
                    "severity": "critical",
                    "message": "SQL injection",
                    "suggestion": "Use parameterized queries",
                },
            ],
        })
        result = parser.parse(content)
        assert len(result.comments) == 2
        assert result.summary == "Found 2 issues"
        assert result.comments[0].file_path == "main.py"
        assert result.comments[0].severity == Severity.WARNING
        assert result.comments[1].severity == Severity.CRITICAL

    def test_parse_response_with_markdown_wrapper(self):
        """测试解析 Markdown 包裹的 JSON。"""
        parser = MultiFormatResponseParser()
        content = '```json\n{"summary": "OK", "comments": []}\n```'
        result = parser.parse(content)
        assert result.summary == "OK"
        assert result.comments == []

    def test_parse_response_invalid_severity_falls_back(self):
        """测试无效严重程度降级为 suggestion。"""
        parser = MultiFormatResponseParser()
        content = json.dumps({
            "summary": "",
            "comments": [{
                "file_path": "a.py",
                "line_start": 1,
                "severity": "unknown_severity",
                "message": "test",
            }],
        })
        result = parser.parse(content)
        assert result.comments[0].severity == Severity.SUGGESTION
        assert any("未知的严重程度" in w for w in result.warnings)

    def test_parse_response_invalid_json(self):
        """测试无效 JSON 抛出异常。"""
        parser = MultiFormatResponseParser()
        with pytest.raises(ValueError, match="所有解析器都无法解析"):
            parser.parse("not json at all")

    def test_build_files_context(self):
        """测试构建文件上下文。"""
        reviewer = self._make_reviewer()
        files = [
            FileChange(path="main.py", added=10, deleted=2, status="modified"),
            FileChange(path="new_module.py", added=50, deleted=0, status="added"),
            FileChange(path="old.py", added=0, deleted=20, status="removed"),
        ]
        context = reviewer._build_files_context(files)
        assert "~ main.py (+10/-2)" in context
        assert "+ new_module.py (+50/-0)" in context
        assert "- old.py (+0/-20)" in context

    def test_multi_format_parser_integration(self):
        """测试多格式解析器与 LiteLLMReviewer 集成。"""
        reviewer = self._make_reviewer()
        # 验证 reviewer 包含多格式解析器
        assert hasattr(reviewer, '_parser')
        assert isinstance(reviewer._parser, MultiFormatResponseParser)
