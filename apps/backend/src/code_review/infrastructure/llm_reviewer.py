"""基于 LiteLLM 的大模型评审器实现。"""

import logging
import time
from uuid import UUID

import litellm

from code_review.core.llm import LLMReviewer, ReviewComment, ReviewResult
from code_review.core.platform import FileChange
from code_review.infrastructure.response_parser import (
    MultiFormatResponseParser,
    ParsedReview,
    ResponseFormat,
)
from code_review.models.config import LLMConfig

logger = logging.getLogger(__name__)

_MAX_USER_CONTENT = 8000   # 请求体中 user message 的最大存储长度（字符）
_MAX_RESPONSE_CONTENT = 4000  # 响应内容的最大存储长度（字符）


async def _save_llm_log(
    session_factory,
    task_id: UUID,
    *,
    provider: str,
    url: str,
    request_body: dict,
    response_status: int,
    response_body: dict,
    status: str,
    error_message: str | None,
    duration_ms: int,
) -> None:
    """将 LLM 调用结果写入 api_call_logs 表。"""
    try:
        from code_review.models.db import ApiCallLog
        async with session_factory() as session:
            log = ApiCallLog(
                task_id=task_id,
                call_type=ApiCallLog.CallType.LLM,
                provider=provider,
                method="POST",
                url=url,
                request_headers={"Authorization": "[REDACTED]", "Content-Type": "application/json"},
                request_body=request_body,
                response_status=response_status,
                response_body=response_body,
                status=status,
                error_message=error_message,
                duration_ms=duration_ms,
            )
            session.add(log)
            await session.commit()
    except Exception as e:
        logger.warning("记录 LLM 调用日志失败: %s", e)


class LiteLLMReviewer(LLMReviewer):
    """使用 LiteLLM 统一接口的大模型评审器。"""

    def __init__(self, config: LLMConfig):
        self._config = config
        self._parser = MultiFormatResponseParser()

    async def review(
        self,
        diff: str,
        files: list[FileChange],
        prompt_template: str,
        task_id: UUID | None = None,
        session_factory=None,
    ) -> ReviewResult:
        start_time = time.time()
        total_tokens = 0
        comments: list[ReviewComment] = []
        summary = ""

        logger.info("=== LiteLLMReviewer.review 被调用 ===")
        logger.info(f"LLMConfig.model: {self._config.model!r}")
        logger.info(f"LLMConfig.api_base: {self._config.api_base!r}")

        files_context = self._build_files_context(files)
        full_prompt = prompt_template.replace("{{diff}}", diff)
        full_prompt = full_prompt.replace("{{files_context}}", files_context)

        kwargs = {
            "model": self._config.model,
            "messages": [
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
            "max_tokens": self._config.max_tokens,
            "timeout": self._config.timeout,
        }

        model_lower = self._config.model.lower()
        skip_temperature_models = [
            "bedrock", "amazon.titan", "anthropic.claude-3-5-sonnet",
            "us.anthropic.claude", "eu.anthropic.claude"
        ]
        if not any(m in model_lower for m in skip_temperature_models):
            kwargs["temperature"] = self._config.temperature

        if self._config.api_key:
            kwargs["api_key"] = self._config.api_key
        if self._config.api_base:
            kwargs["base_url"] = self._config.api_base

        if self._config.extra_params and "custom_llm_provider" in self._config.extra_params:
            kwargs["custom_llm_provider"] = self._config.extra_params["custom_llm_provider"]

        # 构建用于日志记录的请求体（api_key 脱敏，user content 截断）
        log_request_body = {
            "model": self._config.model,
            "max_tokens": self._config.max_tokens,
            "temperature": kwargs.get("temperature"),
            "base_url": self._config.api_base or None,
            "messages": [
                {"role": "system", "content": kwargs["messages"][0]["content"]},
                {"role": "user", "content": full_prompt[:_MAX_USER_CONTENT]},
            ],
        }
        log_url = f"{self._config.api_base}/chat/completions" if self._config.api_base else "litellm"

        t0 = time.perf_counter()
        try:
            response = await litellm.acompletion(**kwargs)
            duration_ms = int((time.perf_counter() - t0) * 1000)

            content = response.choices[0].message.content or ""
            total_tokens = response.usage.total_tokens if response.usage else 0

            logger.info("=== LLM 原始响应 ===")
            logger.info(f"Token 使用量: {total_tokens}")
            logger.info(f"响应内容（前500字符）: {content[:500]}")
            logger.info(f"响应长度: {len(content)} 字符")

            try:
                format_hint = ResponseFormat(self._config.response_format or "auto")
            except ValueError:
                logger.warning(f"无效的响应格式配置: {self._config.response_format}，使用自动检测")
                format_hint = ResponseFormat.AUTO

            parsed_result: ParsedReview = self._parser.parse(content, format_hint=format_hint)
            comments = parsed_result.comments
            summary = parsed_result.summary

            logger.info(
                f"解析完成: 配置格式={self._config.response_format}, "
                f"实际使用格式={parsed_result.format_used.value}, "
                f"评论数={len(comments)}, "
                f"摘要长度={len(summary)}"
            )
            for warning in parsed_result.warnings:
                logger.warning(f"解析警告: {warning}")

            if task_id is not None and session_factory is not None:
                await _save_llm_log(
                    session_factory,
                    task_id,
                    provider=self._config.model,
                    url=log_url,
                    request_body=log_request_body,
                    response_status=200,
                    response_body={
                        "content": content[:_MAX_RESPONSE_CONTENT],
                        "total_tokens": total_tokens,
                        "format_used": parsed_result.format_used.value,
                        "comments_count": len(comments),
                    },
                    status="success",
                    error_message=None,
                    duration_ms=duration_ms,
                )

        except Exception as e:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            logger.error("LLM review failed: %s", e)

            if task_id is not None and session_factory is not None:
                await _save_llm_log(
                    session_factory,
                    task_id,
                    provider=self._config.model,
                    url=log_url,
                    request_body=log_request_body,
                    response_status=0,
                    response_body={},
                    status="failed",
                    error_message=str(e),
                    duration_ms=duration_ms,
                )
            raise

        elapsed = time.time() - start_time
        return ReviewResult(
            comments=comments,
            summary=summary,
            model=self._config.model,
            total_tokens=total_tokens,
            elapsed_seconds=elapsed,
        )

    def _build_files_context(self, files: list[FileChange]) -> str:
        lines = []
        for f in files:
            status_icon = {"added": "+", "modified": "~", "removed": "-", "renamed": "↻"}.get(
                f.status, "?"
            )
            lines.append(f"{status_icon} {f.path} (+{f.added}/-{f.deleted})")
        return "\n".join(lines)

    async def health_check(self) -> bool:
        try:
            kwargs = {
                "model": self._config.model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 5,
                "timeout": 10,
            }
            if self._config.api_key:
                kwargs["api_key"] = self._config.api_key
            if self._config.api_base:
                kwargs["api_base"] = self._config.api_base
            response = await litellm.acompletion(**kwargs)
            return bool(response.choices)
        except Exception as e:
            logger.error("LLM health check failed: %s", e)
            return False
