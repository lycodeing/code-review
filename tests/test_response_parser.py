"""多格式响应解析器单元测试。"""

import pytest

from code_review.core.llm import ReviewComment, Severity
from code_review.infrastructure.response_parser import (
    AnthropicThinkingParser,
    JSONParser,
    MultiFormatResponseParser,
    PlainTextParser,
    ResponseFormat,
    XMLParser,
)


class TestJSONParser:
    """JSON 格式解析器测试。"""

    @pytest.fixture
    def parser(self):
        return JSONParser()

    def test_can_parse_standard_json(self, parser):
        """测试标准 JSON 格式识别。"""
        assert parser.can_parse('{"summary": "test"}')
        assert parser.can_parse('["item1", "item2"]')

    def test_can_parse_markdown_json(self, parser):
        """测试 Markdown 代码块包裹的 JSON。"""
        content = '''```json
{"summary": "test"}
```'''
        assert parser.can_parse(content)

    def test_parse_valid_json(self, parser):
        """测试解析有效的 JSON 响应。"""
        content = '''{
    "summary": "整体评审摘要",
    "comments": [
        {
            "file_path": "src/foo.py",
            "line_start": 10,
            "line_end": 15,
            "severity": "warning",
            "message": "这是一个警告",
            "suggestion": "建议修复"
        }
    ]
}'''
        result = parser.parse(content)

        assert result.format_used == ResponseFormat.JSON
        assert result.summary == "整体评审摘要"
        assert len(result.comments) == 1
        assert result.comments[0].file_path == "src/foo.py"
        assert result.comments[0].line_start == 10
        assert result.comments[0].severity == Severity.WARNING

    def test_parse_markdown_wrapped_json(self, parser):
        """测试解析 Markdown 包裹的 JSON。"""
        content = '''这是一些文本

```json
{
    "summary": "评审摘要",
    "comments": [
        {
            "file_path": "test.py",
            "line_start": 5,
            "line_end": 5,
            "severity": "critical",
            "message": "严重问题",
            "suggestion": "立即修复"
        }
    ]
}
```

更多文本'''
        result = parser.parse(content)

        assert result.format_used == ResponseFormat.JSON
        assert len(result.comments) == 1
        assert result.comments[0].severity == Severity.CRITICAL

    def test_parse_truncated_json_with_bracket_fix(self, parser):
        """测试解析截断的 JSON（自动补全括号）。"""
        content = '{"summary": "test", "comments": []'
        result = parser.parse(content)

        assert result.format_used == ResponseFormat.JSON
        assert len(result.warnings) > 0  # 应该有关于括号补全的警告
        assert result.summary == "test"

    def test_parse_json_with_bom(self, parser):
        """测试解析带 BOM 的 JSON。"""
        content = '\ufeff{"summary": "test", "comments": []}'
        result = parser.parse(content)

        assert result.format_used == ResponseFormat.JSON
        assert len(result.warnings) > 0  # 应该有关于 BOM 移除的警告


class TestAnthropicThinkingParser:
    """Anthropic thinking 格式解析器测试。"""

    @pytest.fixture
    def parser(self):
        return AnthropicThinkingParser()

    def test_can_detect_thinking_format(self, parser):
        """测试识别 Anthropic thinking 格式。"""
        assert parser.can_parse('{"thinking": "some reasoning"}')
        assert parser.can_parse('{"thinking_blocks": [...]}')
        assert parser.can_parse('<thinking>reasoning here</thinking>')

    def test_parse_anthropic_with_thinking_blocks(self, parser):
        """测试解析包含 thinking blocks 的响应。"""
        content = '''{
    "thinking": "这是推理过程",
    "summary": "评审摘要",
    "comments": [
        {
            "file_path": "src/test.py",
            "line_start": 20,
            "line_end": 25,
            "severity": "suggestion",
            "message": "改进建议",
            "suggestion": "优化代码结构"
        }
    ]
}'''
        result = parser.parse(content)

        assert result.format_used == ResponseFormat.ANTHROPIC_THINKING
        assert len(result.warnings) > 0  # 应该有关于 thinking 的警告
        assert len(result.comments) == 1


class TestXMLParser:
    """XML 格式解析器测试。"""

    @pytest.fixture
    def parser(self):
        return XMLParser()

    def test_can_detect_xml_format(self, parser):
        """测试识别 XML 格式。"""
        assert parser.can_parse('<?xml version="1.0"?><root></root>')
        assert parser.can_parse('<review><summary>test</summary></review>')

    def test_parse_valid_xml(self, parser):
        """测试解析有效的 XML 响应。"""
        content = '''<?xml version="1.0"?>
<review>
    <summary>整体评审摘要</summary>
    <comments>
        <comment file_path="src/foo.py" line_start="10" line_end="15" severity="warning">
            <message>这是一个警告</message>
            <suggestion>建议修复</suggestion>
        </comment>
    </comments>
</review>'''
        result = parser.parse(content)

        assert result.format_used == ResponseFormat.XML
        assert result.summary == "整体评审摘要"
        assert len(result.comments) == 1
        assert result.comments[0].file_path == "src/foo.py"


class TestPlainTextParser:
    """纯文本格式解析器测试。"""

    @pytest.fixture
    def parser(self):
        return PlainTextParser()

    def test_always_can_parse(self, parser):
        """测试纯文本解析器总是可以尝试解析。"""
        assert parser.can_parse("任何内容")

    def test_parse_structured_text(self, parser):
        """测试解析结构化文本（中文）。"""
        content = '''摘要: 这是一个代码评审摘要

文件: src/test.py
行: 100-105
严重程度: critical
意见: 发现严重问题
建议: 立即修复此问题'''
        result = parser.parse(content)

        assert result.format_used == ResponseFormat.PLAIN_TEXT
        assert result.summary == "这是一个代码评审摘要"
        assert len(result.comments) == 1
        assert result.comments[0].file_path == "src/test.py"
        assert result.comments[0].severity == Severity.CRITICAL

    def test_parse_english_text(self, parser):
        """测试解析英文结构化文本。"""
        content = '''Summary: Code review summary

file: src/foo.py
line: 50
severity: warning
message: This is a warning
suggestion: Fix the issue'''
        result = parser.parse(content)

        assert result.format_used == ResponseFormat.PLAIN_TEXT
        assert len(result.comments) == 1
        assert result.comments[0].severity == Severity.WARNING


class TestMultiFormatResponseParser:
    """多格式响应解析器集成测试。"""

    @pytest.fixture
    def parser(self):
        return MultiFormatResponseParser()

    def test_auto_detect_and_parse_json(self, parser):
        """测试自动检测并解析 JSON 格式。"""
        content = '{"summary": "test", "comments": []}'
        result = parser.parse(content)

        assert result.format_used == ResponseFormat.JSON
        assert result.summary == "test"

    def test_auto_detect_and_parse_xml(self, parser):
        """测试自动检测并解析 XML 格式。"""
        content = (
            '<?xml version="1.0"?>'
            '<review><summary>test</summary><comments></comments></review>'
        )
        result = parser.parse(content)

        assert result.format_used == ResponseFormat.XML
        assert result.summary == "test"

    def test_fallback_to_plain_text(self, parser):
        """测试降级到纯文本解析。"""
        content = "文件: test.py\n行: 10\n严重程度: warning\n意见: 测试"
        result = parser.parse(content)

        assert result.format_used == ResponseFormat.PLAIN_TEXT

    def test_parse_with_fallback_on_failure(self, parser):
        """测试 parse_with_fallback 方法。"""
        # 无效内容
        content = "完全无法解析的内容"
        fallback_comments = [
            ReviewComment(
                file_path="fallback.py",
                line_start=1,
                line_end=1,
                severity=Severity.INFO,
                message="降级评论",
                suggestion="",
            )
        ]

        result = parser.parse_with_fallback(content, fallback_comments)

        assert result.format_used == ResponseFormat.UNKNOWN
        assert len(result.comments) == 1
        assert result.comments[0].file_path == "fallback.py"
        assert "降级" in result.warnings[0]

    def test_priority_order(self, parser):
        """测试解析器优先级（Anthropic > XML > JSON > Plain Text）。"""
        # 包含 thinking 关键字的内容应该优先使用 Anthropic 解析器
        anthropic_content = '{"thinking": "reasoning", "summary": "test", "comments": []}'
        result = parser.parse(anthropic_content)
        assert result.format_used == ResponseFormat.ANTHROPIC_THINKING


class TestRealWorldExamples:
    """真实场景测试案例。"""

    @pytest.fixture
    def parser(self):
        return MultiFormatResponseParser()

    def test_openai_gpt_response(self, parser):
        """测试 OpenAI GPT 响应格式。"""
        content = '''```json
{
    "summary": "代码整体质量良好，但有一些改进建议",
    "comments": [
        {
            "file_path": "src/models/user.py",
            "line_start": 45,
            "line_end": 50,
            "severity": "warning",
            "message": "缺少输入验证",
            "suggestion": "添加对用户输入的验证逻辑"
        }
    ]
}
```'''
        result = parser.parse(content)

        assert len(result.comments) == 1
        assert result.comments[0].severity == Severity.WARNING
        assert "输入验证" in result.comments[0].message

    def test_anthropic_claude_response(self, parser):
        """测试 Anthropic Claude 响应格式（thinking 模式）。"""
        content = '''{
    "thinking": "让我分析这段代码...",
    "summary": "代码评审完成",
    "comments": [
        {
            "file_path": "src/services/api.py",
            "line_start": 120,
            "line_end": 125,
            "severity": "critical",
            "message": "SQL 注入风险",
            "suggestion": "使用参数化查询"
        }
    ]
}'''
        result = parser.parse(content)

        assert result.format_used == ResponseFormat.ANTHROPIC_THINKING
        assert len(result.comments) == 1
        assert result.comments[0].severity == Severity.CRITICAL
