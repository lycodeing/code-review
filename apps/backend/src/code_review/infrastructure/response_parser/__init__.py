"""多格式 LLM 响应解析器包。

对外导出与原 response_parser.py 完全兼容的接口，调用方无需修改 import 语句。
"""

import logging

from code_review.core.llm import ReviewComment

from .base import ResponseFormat, ParsedReview, ResponseParser
from .json_parser import JSONParser
from .anthropic_parser import AnthropicThinkingParser
from .xml_parser import XMLParser
from .plain_text_parser import PlainTextParser

logger = logging.getLogger(__name__)


class MultiFormatResponseParser:
    """多格式响应解析器（自动检测格式并路由）。"""

    def __init__(self):
        self._parsers = [
            AnthropicThinkingParser(),
            XMLParser(),
            JSONParser(),
            PlainTextParser(),
        ]
        self._format_parser_map = {
            ResponseFormat.JSON: JSONParser(),
            ResponseFormat.ANTHROPIC_THINKING: AnthropicThinkingParser(),
            ResponseFormat.XML: XMLParser(),
            ResponseFormat.PLAIN_TEXT: PlainTextParser(),
        }

    def parse(self, content: str, format_hint: ResponseFormat = ResponseFormat.AUTO) -> ParsedReview:
        logger.info(f"=== 多格式解析器开始 === 内容长度: {len(content)}, 格式提示: {format_hint}")

        if format_hint != ResponseFormat.AUTO and format_hint in self._format_parser_map:
            parser = self._format_parser_map[format_hint]
            logger.info(f"使用指定格式解析器: {parser.__class__.__name__}")
            try:
                result = parser.parse(content)
                self._log_result(result)
                return result
            except Exception as e:
                logger.error(f"指定格式解析器失败: {e}，降级到自动检测")

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

        error_msg = "所有解析器都无法解析该响应内容"
        logger.error(error_msg)
        raise ValueError(error_msg)

    def _log_result(self, result: ParsedReview) -> None:
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
        fallback_comments: list[ReviewComment] | None = None,
        format_hint: ResponseFormat = ResponseFormat.AUTO,
    ) -> ParsedReview:
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


__all__ = [
    "MultiFormatResponseParser",
    "ParsedReview",
    "ResponseFormat",
    "ResponseParser",
    "JSONParser",
    "AnthropicThinkingParser",
    "XMLParser",
    "PlainTextParser",
]
