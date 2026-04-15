"""基于 LiteLLM 的大模型评审器实现。"""

import json
import logging
import time

import litellm

from code_review.core.llm import LLMReviewer, ReviewComment, ReviewResult, Severity
from code_review.core.platform import FileChange
from code_review.models.config import LLMConfig

logger = logging.getLogger(__name__)


class LiteLLMReviewer(LLMReviewer):
    """使用 LiteLLM 统一接口的大模型评审器。

    支持 OpenAI / Anthropic / 通义千问 / DeepSeek / 本地模型等 100+ 提供商。
    只需修改 config.llm.model 和 config.llm.api_base 即可切换。
    """

    def __init__(self, config: LLMConfig):
        self._config = config
        # 配置 LiteLLM
        if config.api_key:
            litellm.api_key = config.api_key
        if config.api_base:
            litellm.api_base = config.api_base

    async def review(
        self,
        diff: str,
        files: list[FileChange],
        prompt_template: str,
    ) -> ReviewResult:
        start_time = time.time()
        total_tokens = 0
        comments: list[ReviewComment] = []
        summary = ""

        # 构建文件上下文
        files_context = self._build_files_context(files)

        # 组装最终 prompt
        full_prompt = prompt_template.replace("{{diff}}", diff)
        full_prompt = full_prompt.replace("{{files_context}}", files_context)

        try:
            response = await litellm.acompletion(
                model=self._config.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert code reviewer. "
                            "Analyze the provided diff and return structured review comments. "
                            "Always respond in valid JSON format."
                        ),
                    },
                    {"role": "user", "content": full_prompt},
                ],
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                timeout=self._config.timeout,
            )

            content = response.choices[0].message.content or ""
            total_tokens = response.usage.total_tokens if response.usage else 0

            # 解析模型返回
            comments, summary = self._parse_response(content)

        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON: %s", e)
            summary = "LLM 返回格式异常，无法解析评审意见。"
        except Exception as e:
            logger.error("LLM review failed: %s", e)
            summary = f"LLM 调用失败: {e}"

        elapsed = time.time() - start_time
        return ReviewResult(
            comments=comments,
            summary=summary,
            model=self._config.model,
            total_tokens=total_tokens,
            elapsed_seconds=elapsed,
        )

    def _build_files_context(self, files: list[FileChange]) -> str:
        """构建文件列表上下文信息。"""
        lines = []
        for f in files:
            status_icon = {"added": "+", "modified": "~", "removed": "-", "renamed": "↻"}.get(
                f.status, "?"
            )
            lines.append(
                f"{status_icon} {f.path} (+{f.added}/-{f.deleted})"
            )
        return "\n".join(lines)

    def _parse_response(self, content: str) -> tuple[list[ReviewComment], str]:
        """解析 LLM 返回的 JSON 格式评审意见。

        期望的 JSON 格式：
        {
            "summary": "整体评审摘要",
            "comments": [
                {
                    "file_path": "src/foo.py",
                    "line_start": 10,
                    "line_end": 15,
                    "severity": "warning",
                    "message": "评审意见",
                    "suggestion": "修复建议"
                }
            ]
        }
        """
        # 尝试提取 JSON 块（兼容 markdown 代码块包裹）
        json_str = content
        if "```json" in content:
            json_str = content.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in content:
            json_str = content.split("```", 1)[1].split("```", 1)[0]

        data = json.loads(json_str.strip())
        summary = data.get("summary", "")

        comments = []
        for item in data.get("comments", []):
            severity_str = item.get("severity", "suggestion").lower()
            try:
                severity = Severity(severity_str)
            except ValueError:
                severity = Severity.SUGGESTION

            comments.append(ReviewComment(
                file_path=item.get("file_path", ""),
                line_start=item.get("line_start", 1),
                line_end=item.get("line_end", item.get("line_start", 1)),
                severity=severity,
                message=item.get("message", ""),
                suggestion=item.get("suggestion", ""),
            ))

        return comments, summary

    async def health_check(self) -> bool:
        try:
            response = await litellm.acompletion(
                model=self._config.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
                timeout=10,
            )
            return bool(response.choices)
        except Exception as e:
            logger.error("LLM health check failed: %s", e)
            return False
