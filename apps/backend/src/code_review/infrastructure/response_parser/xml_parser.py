"""XML 格式 LLM 响应解析器。"""

import logging
import xml.etree.ElementTree as ET

from code_review.core.llm import ReviewComment, Severity
from .base import ResponseParser, ParsedReview, ResponseFormat

logger = logging.getLogger(__name__)


class XMLParser(ResponseParser):
    def can_parse(self, content: str) -> bool:
        content_stripped = content.strip()
        return (
            content_stripped.startswith("<?xml") or
            (content_stripped.startswith("<") and ("</" in content or "/>" in content))
        )

    def parse(self, content: str) -> ParsedReview:
        warnings = []
        comments = []
        summary = ""

        try:
            xml_str = content.strip()
            if "```xml" in content:
                xml_str = content.split("```xml", 1)[1].split("```", 1)[0].strip()
            elif "```" in content:
                xml_str = content.split("```", 1)[1].split("```", 1)[0].strip()

            root = ET.fromstring(xml_str)
            summary_elem = root.find("summary")
            if summary_elem is not None and summary_elem.text:
                summary = summary_elem.text

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
                    line_end = int(comment_elem.get("line_end", comment_elem.get("line_start", 1)))
                    comments.append(ReviewComment(
                        file_path=comment_elem.get("file_path", ""),
                        line_start=line_start,
                        line_end=line_end,
                        severity=severity,
                        message=comment_elem.findtext("message", ""),
                        suggestion=comment_elem.findtext("suggestion", ""),
                    ))

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
