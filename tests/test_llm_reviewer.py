"""LLM 评审器测试。"""

import json
import pytest

from code_review.core.llm import Severity
from code_review.core.platform import FileChange
from code_review.infrastructure.llm_reviewer import LiteLLMReviewer
from code_review.models.config import LLMConfig


class TestLiteLLMReviewer:
    """LLM 评审器解析逻辑测试。"""

    def _make_reviewer(self) -> LiteLLMReviewer:
        config = LLMConfig(model="gpt-4", api_key="test-key")
        return LiteLLMReviewer(config)

    def test_parse_response_valid_json(self):
        reviewer = self._make_reviewer()
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
        comments, summary = reviewer._parse_response(content)
        assert len(comments) == 2
        assert summary == "Found 2 issues"
        assert comments[0].file_path == "main.py"
        assert comments[0].severity == Severity.WARNING
        assert comments[1].severity == Severity.CRITICAL

    def test_parse_response_with_markdown_wrapper(self):
        reviewer = self._make_reviewer()
        content = '```json\n{"summary": "OK", "comments": []}\n```'
        comments, summary = reviewer._parse_response(content)
        assert summary == "OK"
        assert comments == []

    def test_parse_response_invalid_severity_falls_back(self):
        reviewer = self._make_reviewer()
        content = json.dumps({
            "summary": "",
            "comments": [{
                "file_path": "a.py",
                "line_start": 1,
                "severity": "unknown_severity",
                "message": "test",
            }],
        })
        comments, _ = reviewer._parse_response(content)
        assert comments[0].severity == Severity.SUGGESTION

    def test_parse_response_invalid_json(self):
        reviewer = self._make_reviewer()
        comments, summary = reviewer._parse_response("not json at all")
        assert comments == []

    def test_build_files_context(self):
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
