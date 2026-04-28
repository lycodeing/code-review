"""纯文本格式 LLM 响应解析器（正则提取，降级方案）。"""

import logging
import re

from code_review.core.llm import ReviewComment, Severity
from .base import ResponseParser, ParsedReview, ResponseFormat

logger = logging.getLogger(__name__)


class PlainTextParser(ResponseParser):
    COMMENT_PATTERN = re.compile(
        r'(?:文件|file|路径|path)[:\s]+([^\n\r]+)[\r\n]+'
        r'(?:行|line)[:\s]+(\d+)(?:-(\d+))?[\r\n]+'
        r'(?:严重程度|severity|级别)[:\s]+(\w+)[\r\n]+'
        r'(?:意见|message|描述|description)[:\s]+([^\n\r]+)(?:[\r\n]+'
        r'(?:建议|suggestion)[:\s]+([^\n\r]+))?',
        re.IGNORECASE,
    )
    SUMMARY_PATTERN = re.compile(
        r'(?:摘要|summary|总结)[:\s]+([^\n\r]+)',
        re.IGNORECASE,
    )

    def can_parse(self, content: str) -> bool:
        """兜底解析器，永远返回 True。

        此解析器必须排在解析器列表的最后位置，仅在所有其他解析器均无法处理内容时
        作为最终降级方案使用。通过正则表达式提取结构化评审意见，准确性相对较低。
        """
        return True

    def parse(self, content: str) -> ParsedReview:
        warnings = ["使用纯文本解析器（正则提取），准确性可能降低"]
        comments = []
        summary = ""

        summary_match = self.SUMMARY_PATTERN.search(content)
        if summary_match:
            summary = summary_match.group(1).strip()

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

        logger.info(f"纯文本解析完成: {len(comments)} 条评审意见")
        return ParsedReview(
            comments=comments,
            summary=summary,
            format_used=ResponseFormat.PLAIN_TEXT,
            raw_content=content,
            warnings=warnings,
        )
