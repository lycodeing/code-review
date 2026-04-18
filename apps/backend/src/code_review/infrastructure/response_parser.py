"""多格式 LLM 响应解析器。

支持解析多种 LLM 返回格式，自动识别并处理：
- 标准 JSON 格式（OpenAI、Zhipu、DeepSeek 等）
- Anthropic 格式（包含 thinking blocks）
- XML 格式
- 纯文本格式（带正则提取）

关键特性：
- 自动修复 LLM 常见的 JSON 格式错误（未转义换行符、截断等）
- 宽松的格式检测和容错处理
- 详细的调试日志
"""

import json
import logging
import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum

from code_review.core.llm import ReviewComment, Severity

logger = logging.getLogger(__name__)


class ResponseFormat(StrEnum):
    """响应格式类型。"""
    AUTO = "auto"
    JSON = "json"
    ANTHROPIC_THINKING = "anthropic_thinking"
    XML = "xml"
    PLAIN_TEXT = "plain_text"
    UNKNOWN = "unknown"


@dataclass
class ParsedReview:
    """解析后的评审结果。"""
    comments: list[ReviewComment]
    summary: str
    format_used: ResponseFormat
    raw_content: str
    warnings: list[str] = field(default_factory=list)


class ResponseParser(ABC):
    """响应解析器抽象基类。"""

    @abstractmethod
    def can_parse(self, content: str) -> bool:
        """判断是否能解析该内容。"""
        pass

    @abstractmethod
    def parse(self, content: str) -> ParsedReview:
        """解析内容并返回统一的评审结果。"""
        pass


def fix_json_string(content: str) -> tuple[str, list[str]]:
    """修复 JSON 字符串中的常见错误。

    返回: (修复后的字符串, 警告列表)
    """
    warnings = []

    # 1. 提取 JSON 内容（兼容 markdown 代码块）
    json_str = extract_json_block(content)

    # 2. 修复未转义的换行符（LLM 最常见的错误）
    json_str, newline_fixes = fix_unescaped_newlines(json_str)
    if newline_fixes > 0:
        warnings.append(f"修复了 {newline_fixes} 处未转义的换行符")

    # 3. 移除 BOM 标记
    if json_str.startswith('\ufeff'):
        json_str = json_str[1:]
        warnings.append("移除了 BOM 标记")

    # 4. 修复截断的 JSON（补全括号）
    json_str, truncation_fixes = fix_truncated_json(json_str)
    if truncation_fixes > 0:
        warnings.append(f"修复了 {truncation_fixes} 处未闭合的括号")

    return json_str, warnings


def extract_json_block(content: str) -> str:
    """提取 JSON 块（兼容 markdown 代码块）。"""
    json_str = content.strip()

    # 如果整个内容就是一个 JSON 对象/数组，直接返回
    if json_str.startswith('{') or json_str.startswith('['):
        return json_str

    # 尝试提取 ```json 代码块
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
    """修复 JSON 字符串值中的未转义换行符。

    使用状态机遍历，在字符串内部将真实的换行符替换为 \\n。
    """
    result = []
    i = 0
    n = len(json_str)
    in_string = False
    escape_next = False
    fixed_count = 0

    while i < n:
        char = json_str[i]

        if escape_next:
            # 上一个字符是反斜杠，这个字符被转义
            result.append(char)
            escape_next = False
        elif char == '\\':
            # 遇到转义字符
            result.append(char)
            escape_next = True
        elif char == '"':
            # 引号：切换字符串状态
            result.append(char)
            in_string = not in_string
        elif in_string and char in '\n\r\t':
            # 在字符串内部遇到未转义的控制字符
            if char == '\n':
                result.append('\\n')
            elif char == '\r':
                result.append('\\r')
            elif char == '\t':
                result.append('\\t')
            fixed_count += 1
        else:
            # 其他字符直接添加
            result.append(char)

        i += 1

    return ''.join(result), fixed_count


def fix_truncated_json(json_str: str) -> tuple[str, int]:
    """修复截断的 JSON（补全未闭合的括号）。

    如果检测到未闭合的字符串，会截断到上一个完整位置。
    """
    fixes = 0

    # 首先检测是否有未闭合的字符串
    # 从后往前扫描，找到最后一个完整的字符串结束位置
    has_unclosed_string = False
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
                # 找到字符串结束位置，这是好的
                break
        # 忽略其他字符

    # 如果扫描结束后仍在字符串内，说明有未闭合的字符串
    # 需要截断
    if in_string:
        logger.info("检测到未闭合的字符串，尝试截断到上一个完整位置")

        # 从后往前找最后一个完整的对象
        # 简单策略：找到倒数第二个 "}" 并在其后闭合
        last_brace_pos = json_str.rfind('}')
        if last_brace_pos != -1:
            # 在最后一个 } 之后截断，然后补全
            second_last_brace = json_str.rfind('}', 0, last_brace_pos)
            if second_last_brace != -1:
                # 截断到第二个最后一个 } 之后
                json_str = json_str[:second_last_brace + 1]
                # 这时可能缺少数组的闭合，继续处理
                fixes += 100  # 标记进行了截断
                logger.info(f"截断 JSON 到位置 {second_last_brace}")

    # 计算括号数量并补全
    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    open_brackets = json_str.count('[')
    close_brackets = json_str.count(']')

    # 补全花括号
    if open_braces > close_braces:
        json_str += '}' * (open_braces - close_braces)
        fixes += open_braces - close_braces

    # 补全方括号
    if open_brackets > close_brackets:
        json_str += ']' * (open_brackets - close_brackets)
        fixes += open_brackets - close_brackets

    return json_str, fixes


def parse_comments_list(comments_data: list) -> tuple[list[ReviewComment], list[str]]:
    """解析评论列表（兼容不同字段名）。"""
    warnings = []
    comments = []

    for item in comments_data:
        try:
            # 兼容不同字段名
            file_path = item.get("file_path") or item.get("path") or ""
            line_start = item.get("line_start") or item.get("line", 1)
            line_end = item.get("line_end") or item.get("line", line_start)
            message = item.get("message") or item.get("comment") or item.get("text") or ""
            suggestion = item.get("suggestion") or ""

            # 解析严重程度
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


class JSONParser(ResponseParser):
    """JSON 格式解析器（容错性强）。"""

    def can_parse(self, content: str) -> bool:
        """判断是否为 JSON 格式。"""
        content_stripped = content.strip()
        return (
            content_stripped.startswith("{") or
            content_stripped.startswith("[") or
            "```json" in content or
            "```" in content
        )

    def parse(self, content: str) -> ParsedReview:
        """解析 JSON 格式响应。"""
        warnings = []

        # 1. 修复 JSON
        json_str, fix_warnings = fix_json_string(content)
        warnings.extend(fix_warnings)

        logger.info(f"JSON 修复完成，内容长度: {len(json_str)}")
        logger.debug(f"修复后的 JSON（前200字符）: {json_str[:200]}")

        # 2. 尝试解析
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            logger.info(f"失败的 JSON 内容（最后200字符）: {json_str[-200:]}")

            # 尝试尽力而为的解析
            data = self._try_partial_parse(json_str, warnings)
            if data is None:
                # 即使完全失败，也尝试返回空结果而不是抛出异常
                logger.warning("完全无法解析 JSON，返回空结果")
                return ParsedReview(
                    comments=[],
                    summary="JSON 解析完全失败，无法提取评审意见",
                    format_used=ResponseFormat.JSON,
                    raw_content=content,
                    warnings=[f"JSON 解析失败: {e}", "返回了空结果"],
                )

        # 3. 提取数据
        summary = data.get("summary", "")
        if not summary and isinstance(data, dict):
            summary = "无法提取摘要"

        comments_data = data.get("comments", [])
        if not isinstance(comments_data, list):
            comments_data = []

        comments, parse_warnings = parse_comments_list(comments_data)
        warnings.extend(parse_warnings)

        logger.info(f"JSON 解析成功: {len(comments)} 条评审意见")
        return ParsedReview(
            comments=comments,
            summary=summary,
            format_used=ResponseFormat.JSON,
            raw_content=content,
            warnings=warnings,
        )

    def _try_partial_parse(self, json_str: str, warnings: list[str]) -> dict | None:
        """尝试从截断的 JSON 中提取部分数据。

        策略：
        1. 找到 comments 数组
        2. 遍历数组，提取完整的对象
        3. 跳过不完整的对象
        """
        try:
            # 查找 comments 数组
            comments_start = json_str.find('"comments"')
            if comments_start == -1:
                logger.warning("未找到 comments 字段")
                return None

            array_start = json_str.find('[', comments_start)
            if array_start == -1:
                logger.warning("未找到 comments 数组开始标记")
                return None

            # 使用栈跟踪完整对象
            stack = []
            complete_objects = []
            current_obj_start = -1
            in_string = False
            escape_next = False

            for i in range(array_start, len(json_str)):
                char = json_str[i]

                # 处理转义字符
                if escape_next:
                    escape_next = False
                    continue

                if char == '\\' and in_string:
                    escape_next = True
                    continue

                # 处理字符串边界
                if char == '"' and not escape_next:
                    in_string = not in_string
                    if not in_string and not stack:
                        # 字符串结束但不在任何嵌套中，这可能是数组元素分隔符
                        pass
                    continue

                # 如果在字符串内，忽略其他字符
                if in_string:
                    continue

                # 处理括号
                if char == '{':
                    if not stack:
                        current_obj_start = i
                    stack.append('{')
                elif char == '}':
                    if stack and stack[-1] == '{':
                        stack.pop()
                        if not stack:
                            # 找到一个完整的对象
                            obj_str = json_str[current_obj_start:i+1]
                            try:
                                obj = json.loads(obj_str)
                                complete_objects.append(obj)
                                logger.debug(f"提取完整对象 {len(complete_objects)}: {obj.get('file_path', 'unknown')}")
                            except json.JSONDecodeError as e:
                                logger.warning(f"无法解析对象: {e}")
                elif char == '[':
                    stack.append('[')
                elif char == ']':
                    if stack and stack[-1] == '[':
                        stack.pop()
                        if not stack:
                            # 数组结束
                            logger.info(f"到达数组结束，提取了 {len(complete_objects)} 个完整对象")
                            break

            if complete_objects:
                warnings.append(f"从截断响应中提取了 {len(complete_objects)} 条完整评论")
                return {
                    "summary": "响应被截断，仅包含部分评审意见",
                    "comments": complete_objects
                }
            else:
                logger.warning("未能提取任何完整对象")
                return None

        except Exception as e:
            logger.warning(f"部分解析异常: {e}")
            return None


class AnthropicThinkingParser(ResponseParser):
    """Anthropic 格式解析器（处理 thinking blocks）。"""

    def can_parse(self, content: str) -> bool:
        """判断是否为 Anthropic thinking 格式。"""
        keywords = ["thinking", "reasoning_content", "thinking_blocks", "<thinking>"]
        content_lower = content.lower()
        return any(k in content_lower for k in keywords)

    def parse(self, content: str) -> ParsedReview:
        """解析 Anthropic thinking 格式响应。"""
        warnings = []
        comments = []
        summary = ""

        try:
            # 尝试提取 JSON
            data = self._extract_json(content)

            if isinstance(data, dict):
                summary = data.get("summary", "")

                # 忽略 thinking 相关字段
                if any(k in data for k in ["thinking", "reasoning_content", "thinking_blocks"]):
                    warnings.append("检测到 thinking blocks，已忽略推理过程")

                # 提取 comments（可能在顶层或 content 内）
                comments_data = data.get("comments", [])

                if not comments_data and "content" in data:
                    content_array = data["content"]
                    if isinstance(content_array, list):
                        for block in content_array:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text = block.get("text", "")
                                if text:
                                    try:
                                        embedded_data = json.loads(text)
                                        if "comments" in embedded_data:
                                            comments_data = embedded_data["comments"]
                                            if not summary:
                                                summary = embedded_data.get("summary", "")
                                            break
                                    except json.JSONDecodeError:
                                        pass

                comments, parse_warnings = parse_comments_list(comments_data)
                warnings.extend(parse_warnings)

            logger.info(f"Anthropic 格式解析成功: {len(comments)} 条评审意见")
            return ParsedReview(
                comments=comments,
                summary=summary,
                format_used=ResponseFormat.ANTHROPIC_THINKING,
                raw_content=content,
                warnings=warnings,
            )

        except Exception as e:
            logger.error(f"Anthropic 格式解析失败: {e}")
            raise

    def _extract_json(self, content: str) -> dict:
        """提取 JSON 数据。"""
        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试提取代码块
        if "```json" in content:
            json_str = content.split("```json", 1)[1].split("```", 1)[0]
            return json.loads(json_str.strip())
        elif "```" in content:
            json_str = content.split("```", 1)[1].split("```", 1)[0]
            return json.loads(json_str.strip())

        raise ValueError("无法提取有效的 JSON")


class XMLParser(ResponseParser):
    """XML 格式解析器。"""

    def can_parse(self, content: str) -> bool:
        """判断是否为 XML 格式。"""
        content_stripped = content.strip()
        return (
            content_stripped.startswith("<?xml") or
            (content_stripped.startswith("<") and ("</" in content or "/>" in content))
        )

    def parse(self, content: str) -> ParsedReview:
        """解析 XML 格式响应。"""
        warnings = []
        comments = []
        summary = ""

        try:
            # 提取 XML 部分
            xml_str = content.strip()
            if "```xml" in content:
                xml_str = content.split("```xml", 1)[1].split("```", 1)[0].strip()
            elif "```" in content:
                xml_str = content.split("```", 1)[1].split("```", 1)[0].strip()

            # 解析 XML
            root = ET.fromstring(xml_str)

            # 提取 summary
            summary_elem = root.find("summary")
            if summary_elem is not None and summary_elem.text:
                summary = summary_elem.text

            # 提取 comments
            comments_elem = root.find("comments")
            if comments_elem is not None:
                for comment_elem in comments_elem.findall("comment"):
                    severity_str = comment_elem.get("severity", "suggestion").lower()
                    try:
                        severity = Severity(severity_str)
                    except ValueError:
                        severity = Severity.SUGGESTION
                        warnings.append(f"未知的严重程度: {severity_str}")

                    line_start = int(comment_elem.get("line_start", 1))
                    line_end = int(
                        comment_elem.get("line_end", comment_elem.get("line_start", 1))
                    )

                    comments.append(
                        ReviewComment(
                            file_path=comment_elem.get("file_path", ""),
                            line_start=line_start,
                            line_end=line_end,
                            severity=severity,
                            message=comment_elem.findtext("message", ""),
                            suggestion=comment_elem.findtext("suggestion", ""),
                        )
                    )

            logger.info(f"XML 解析成功: {len(comments)} 条评审意见")
            return ParsedReview(
                comments=comments,
                summary=summary,
                format_used=ResponseFormat.XML,
                raw_content=content,
                warnings=warnings,
            )

        except ET.ParseError as e:
            logger.error(f"XML 解析失败: {e}")
            raise ValueError(f"XML 解析失败: {e}")


class PlainTextParser(ResponseParser):
    """纯文本格式解析器（正则提取，作为最后的降级方案）。"""

    # 改进的正则模式，支持多行匹配
    COMMENT_PATTERN = re.compile(
        r'(?:文件|file|路径|path)[:\s]+([^\n\r]+)[\r\n]+'
        r'(?:行|line)[:\s]+(\d+)(?:-(\d+))?[\r\n]+'
        r'(?:严重程度|severity|级别)[:\s]+(\w+)[\r\n]+'
        r'(?:意见|message|描述|description)[:\s]+([^\n\r]+)(?:[\r\n]+'
        r'(?:建议|suggestion)[:\s]+([^\n\r]+))?',
        re.IGNORECASE
    )

    SUMMARY_PATTERN = re.compile(
        r'(?:摘要|summary|总结)[:\s]+([^\n\r]+)',
        re.IGNORECASE
    )

    def can_parse(self, content: str) -> bool:
        """纯文本解析器总是可以尝试。"""
        return True

    def parse(self, content: str) -> ParsedReview:
        """解析纯文本格式响应。"""
        warnings = ["使用纯文本解析器（正则提取），准确性可能降低"]
        comments = []
        summary = ""

        # 提取 summary
        summary_match = self.SUMMARY_PATTERN.search(content)
        if summary_match:
            summary = summary_match.group(1).strip()

        # 提取 comments
        for match in self.COMMENT_PATTERN.finditer(content):
            try:
                file_path = match.group(1).strip()
                line_start = int(match.group(2))
                line_end = int(match.group(3)) if match.group(3) else line_start
                severity_str = match.group(4).lower()
                message = match.group(5).strip()
                suggestion = match.group(6).strip() if match.group(6) else ""

                try:
                    severity = Severity(severity_str)
                except ValueError:
                    severity = Severity.SUGGESTION

                if line_start > 0 and file_path:
                    comments.append(ReviewComment(
                        file_path=file_path,
                        line_start=line_start,
                        line_end=line_end,
                        severity=severity,
                        message=message,
                        suggestion=suggestion,
                    ))
            except (ValueError, AttributeError) as e:
                warnings.append(f"跳过无效的评论匹配: {e}")

        if not comments:
            warnings.append("未能从文本中提取任何评审意见")
            logger.warning("纯文本解析器未能提取任何评审意见")
            raise ValueError("纯文本解析器未能提取任何评审意见")

        logger.info(f"纯文本解析完成: {len(comments)} 条评审意见")
        return ParsedReview(
            comments=comments,
            summary=summary,
            format_used=ResponseFormat.PLAIN_TEXT,
            raw_content=content,
            warnings=warnings,
        )


class MultiFormatResponseParser:
    """多格式响应解析器（自动检测格式并路由）。"""

    def __init__(self):
        # 按优先级排序的解析器列表
        self._parsers = [
            AnthropicThinkingParser(),
            XMLParser(),
            JSONParser(),
            PlainTextParser(),
        ]

        # 格式到解析器的映射
        self._format_parser_map = {
            ResponseFormat.JSON: JSONParser(),
            ResponseFormat.ANTHROPIC_THINKING: AnthropicThinkingParser(),
            ResponseFormat.XML: XMLParser(),
            ResponseFormat.PLAIN_TEXT: PlainTextParser(),
        }

    def parse(self, content: str, format_hint: ResponseFormat = ResponseFormat.AUTO) -> ParsedReview:
        """自动检测格式并解析响应。

        Args:
            content: LLM 返回的原始内容
            format_hint: 可选的格式提示

        Returns:
            ParsedReview: 解析后的评审结果

        Raises:
            ValueError: 所有解析器都无法解析时
        """
        logger.info("=== 多格式解析器开始 ===")
        logger.info(f"内容长度: {len(content)} 字符, 格式提示: {format_hint}")
        logger.info(f"内容预览（前300字符）: {content[:300]}")

        # 如果指定了格式，直接使用对应的解析器
        if format_hint != ResponseFormat.AUTO and format_hint in self._format_parser_map:
            parser = self._format_parser_map[format_hint]
            logger.info(f"使用指定格式解析器: {parser.__class__.__name__}")
            try:
                result = parser.parse(content)
                self._log_result(result)
                return result
            except Exception as e:
                logger.error(f"指定格式解析器失败: {e}，降级到自动检测")

        # 自动检测格式
        for parser in self._parsers:
            try:
                if parser.can_parse(content):
                    logger.info(f"尝试 {parser.__class__.__name__}")
                    result = parser.parse(content)
                    self._log_result(result)
                    return result
            except Exception as e:
                logger.info(f"{parser.__class__.__name__} 失败: {e}")
                continue

        # 所有解析器都失败
        error_msg = "所有解析器都无法解析该响应内容"
        logger.error(error_msg)
        raise ValueError(error_msg)

    def _log_result(self, result: ParsedReview) -> None:
        """记录解析结果。"""
        for warning in result.warnings:
            logger.warning(f"解析警告: {warning}")

        logger.info(
            f"解析成功: 格式={result.format_used.value}, "
            f"评论数={len(result.comments)}, "
            f"摘要长度={len(result.summary)}"
        )

    def parse_with_fallback(
        self,
        content: str,
        fallback_comments: list[ReviewComment] = None,
        format_hint: ResponseFormat = ResponseFormat.AUTO,
    ) -> ParsedReview:
        """带降级方案的解析。

        如果所有解析器都失败，返回降级结果。
        """
        try:
            return self.parse(content, format_hint=format_hint)
        except Exception as e:
            logger.warning(f"解析失败，使用降级方案: {e}")
            return ParsedReview(
                comments=fallback_comments or [],
                summary=f"解析失败: {str(e)}",
                format_used=ResponseFormat.UNKNOWN,
                raw_content=content,
                warnings=[f"解析失败，已使用降级方案: {str(e)}"],
            )
