"""JSON 格式 LLM 响应解析器。"""

import json
import logging

from .base import ResponseParser, ParsedReview, ResponseFormat, fix_json_string, parse_comments_list

logger = logging.getLogger(__name__)


class JSONParser(ResponseParser):
    def can_parse(self, content: str) -> bool:
        content_stripped = content.strip()
        return (
            content_stripped.startswith("{") or
            content_stripped.startswith("[") or
            "```json" in content or
            "```" in content
        )

    def parse(self, content: str) -> ParsedReview:
        warnings = []
        json_str, fix_warnings = fix_json_string(content)
        warnings.extend(fix_warnings)
        logger.info(f"JSON 修复完成，内容长度: {len(json_str)}")

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            data = self._try_partial_parse(json_str, warnings)
            if data is None:
                logger.warning("完全无法解析 JSON，返回空结果")
                return ParsedReview(
                    comments=[],
                    summary="JSON 解析完全失败，无法提取评审意见",
                    format_used=ResponseFormat.JSON,
                    raw_content=content,
                    warnings=[f"JSON 解析失败: {e}", "返回了空结果"],
                )

        summary = data.get("summary", "") if isinstance(data, dict) else ""
        if not summary:
            summary = "无法提取摘要"
        comments_data = data.get("comments", []) if isinstance(data, dict) else []
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
        try:
            comments_start = json_str.find('"comments"')
            if comments_start == -1:
                return None
            array_start = json_str.find('[', comments_start)
            if array_start == -1:
                return None

            stack = []
            complete_objects = []
            current_obj_start = -1
            in_string = False
            escape_next = False

            for i in range(array_start, len(json_str)):
                char = json_str[i]
                if escape_next:
                    escape_next = False
                    continue
                if char == '\\' and in_string:
                    escape_next = True
                    continue
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if char == '{':
                    if not stack:
                        current_obj_start = i
                    stack.append('{')
                elif char == '}':
                    if stack and stack[-1] == '{':
                        stack.pop()
                        if not stack:
                            obj_str = json_str[current_obj_start:i + 1]
                            try:
                                complete_objects.append(json.loads(obj_str))
                            except json.JSONDecodeError:
                                pass
                elif char == '[':
                    stack.append('[')
                elif char == ']':
                    if stack and stack[-1] == '[':
                        stack.pop()
                        if not stack:
                            break

            if complete_objects:
                warnings.append(f"从截断响应中提取了 {len(complete_objects)} 条完整评论")
                return {"summary": "响应被截断，仅包含部分评审意见", "comments": complete_objects}
            return None
        except Exception as e:
            logger.warning(f"部分解析异常: {e}")
            return None
