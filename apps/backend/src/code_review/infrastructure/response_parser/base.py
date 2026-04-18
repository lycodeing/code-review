"""响应解析器基础类型、枚举和共享工具函数。"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum

from code_review.core.llm import ReviewComment, Severity

logger = logging.getLogger(__name__)


class ResponseFormat(StrEnum):
    AUTO = "auto"
    JSON = "json"
    ANTHROPIC_THINKING = "anthropic_thinking"
    XML = "xml"
    PLAIN_TEXT = "plain_text"
    UNKNOWN = "unknown"


@dataclass
class ParsedReview:
    comments: list[ReviewComment]
    summary: str
    format_used: ResponseFormat
    raw_content: str
    warnings: list[str] = field(default_factory=list)


class ResponseParser(ABC):
    @abstractmethod
    def can_parse(self, content: str) -> bool:
        """判断该解析器是否能处理给定内容。

        返回 True 表示该解析器可以尝试解析此内容，此时调用 parse() 应能成功。
        注意：PlainTextParser 是例外，它永远返回 True 作为兜底解析器，
        因此必须排在解析器列表的最后位置。
        """
        ...

    @abstractmethod
    def parse(self, content: str) -> ParsedReview:
        """解析 LLM 响应内容并返回结构化评审结果。

        解析成功返回 ParsedReview，失败时抛出 ValueError。
        """
        ...


def extract_json_block(content: str) -> str:
    json_str = content.strip()
    if json_str.startswith('{') or json_str.startswith('['):
        return json_str
    if "```json" in content:
        parts = content.split("```json", 1)
        if len(parts) > 1:
            json_str = parts[1].split("```", 1)[0]
    elif "```" in content:
        parts = content.split("```", 1)
        if len(parts) > 1:
            json_str = parts[1].split("```", 1)[0]
    return json_str.strip()


def fix_unescaped_newlines(json_str: str) -> tuple[str, int]:
    result = []
    i = 0
    n = len(json_str)
    in_string = False
    escape_next = False
    fixed_count = 0

    while i < n:
        char = json_str[i]
        if escape_next:
            result.append(char)
            escape_next = False
        elif char == '\\':
            result.append(char)
            escape_next = True
        elif char == '"':
            result.append(char)
            in_string = not in_string
        elif in_string and char in '\n\r\t':
            if char == '\n':
                result.append('\\n')
            elif char == '\r':
                result.append('\\r')
            elif char == '\t':
                result.append('\\t')
            fixed_count += 1
        else:
            result.append(char)
        i += 1

    return ''.join(result), fixed_count


def fix_truncated_json(json_str: str) -> tuple[str, int]:
    fixes = 0
    in_string = False
    escape_next = False

    for i in range(len(json_str) - 1, -1, -1):
        char = json_str[i]
        if escape_next:
            escape_next = False
            continue
        if char == '\\':
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            if not in_string:
                break

    if in_string:
        logger.info("检测到未闭合的字符串，尝试截断到上一个完整位置")
        last_brace_pos = json_str.rfind('}')
        if last_brace_pos != -1:
            second_last_brace = json_str.rfind('}', 0, last_brace_pos)
            if second_last_brace != -1:
                json_str = json_str[:second_last_brace + 1]
                fixes += 100
                logger.info(f"截断 JSON 到位置 {second_last_brace}")

    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    open_brackets = json_str.count('[')
    close_brackets = json_str.count(']')

    if open_braces > close_braces:
        json_str += '}' * (open_braces - close_braces)
        fixes += open_braces - close_braces
    if open_brackets > close_brackets:
        json_str += ']' * (open_brackets - close_brackets)
        fixes += open_brackets - close_brackets

    return json_str, fixes


def fix_json_string(content: str) -> tuple[str, list[str]]:
    warnings = []
    json_str = extract_json_block(content)
    json_str, newline_fixes = fix_unescaped_newlines(json_str)
    if newline_fixes > 0:
        warnings.append(f"修复了 {newline_fixes} 处未转义的换行符")
    if json_str.startswith('\ufeff'):
        json_str = json_str[1:]
        warnings.append("移除了 BOM 标记")
    json_str, truncation_fixes = fix_truncated_json(json_str)
    if truncation_fixes > 0:
        warnings.append(f"修复了 {truncation_fixes} 处未闭合的括号")
    return json_str, warnings


def parse_comments_list(comments_data: list) -> tuple[list[ReviewComment], list[str]]:
    warnings = []
    comments = []
    for item in comments_data:
        try:
            file_path = item.get("file_path") or item.get("path") or ""
            line_start = item.get("line_start") or item.get("line", 1)
            line_end = item.get("line_end") or item.get("line", line_start)
            message = item.get("message") or item.get("comment") or item.get("text") or ""
            suggestion = item.get("suggestion") or ""
            severity_str = item.get("severity", "suggestion").lower()
            try:
                severity = Severity(severity_str)
            except ValueError:
                severity = Severity.SUGGESTION
                warnings.append(f"未知的严重程度: {severity_str}")
            comments.append(ReviewComment(
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                severity=severity,
                message=message,
                suggestion=suggestion,
            ))
        except Exception as e:
            warnings.append(f"跳过无效评论: {e}")
    return comments, warnings
