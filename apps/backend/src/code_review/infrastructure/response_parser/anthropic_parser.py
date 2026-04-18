"""Anthropic thinking 格式 LLM 响应解析器。"""

import json
import logging

from .base import ResponseParser, ParsedReview, ResponseFormat, parse_comments_list

logger = logging.getLogger(__name__)


class AnthropicThinkingParser(ResponseParser):
    def can_parse(self, content: str) -> bool:
        keywords = ["thinking", "reasoning_content", "thinking_blocks", "<thinking>"]
        content_lower = content.lower()
        return any(k in content_lower for k in keywords)

    def parse(self, content: str) -> ParsedReview:
        warnings = []
        comments = []
        summary = ""

        try:
            data = self._extract_json(content)
            if isinstance(data, dict):
                summary = data.get("summary", "")
                if any(k in data for k in ["thinking", "reasoning_content", "thinking_blocks"]):
                    warnings.append("检测到 thinking blocks，已忽略推理过程")
                comments_data = data.get("comments", [])
                if not comments_data and "content" in data:
                    for block in data["content"]:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if text:
                                try:
                                    embedded = json.loads(text)
                                    if "comments" in embedded:
                                        comments_data = embedded["comments"]
                                        if not summary:
                                            summary = embedded.get("summary", "")
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
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        if "```json" in content:
            return json.loads(content.split("```json", 1)[1].split("```", 1)[0].strip())
        elif "```" in content:
            return json.loads(content.split("```", 1)[1].split("```", 1)[0].strip())
        raise ValueError("无法提取有效的 JSON")
