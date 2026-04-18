"""基于 LiteLLM 的大模型评审器实现。"""

import logging
import time

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


class LiteLLMReviewer(LLMReviewer):
    """使用 LiteLLM 统一接口的大模型评审器。

    支持 OpenAI / Anthropic / 通义千问 / DeepSeek / 本地模型等 100+ 提供商。
    只需修改 config.llm.model 和 config.llm.api_base 即可切换。

    多格式支持：
    - OpenAI 格式（标准 JSON）
    - Anthropic 格式（包含 thinking blocks、reasoning_content）
    - XML 格式
    - 纯文本格式（带正则提取）
    """

    def __init__(self, config: LLMConfig):
        self._config = config
        self._parser = MultiFormatResponseParser()

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

        # 调试日志
        logger.info("=== LiteLLMReviewer.review 被调用 ===")
        logger.info(f"LLMConfig.model: {self._config.model!r}")
        logger.info(f"LLMConfig.api_base: {self._config.api_base!r}")

        # 构建文件上下文
        files_context = self._build_files_context(files)

        # 组装最终 prompt
        full_prompt = prompt_template.replace("{{diff}}", diff)
        full_prompt = full_prompt.replace("{{files_context}}", files_context)

        try:
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

            # 某些模型（如 AWS Bedrock 的某些模型）不支持 temperature 参数
            # 只在模型支持时添加 temperature
            model_lower = self._config.model.lower()
            skip_temperature_models = [
                "bedrock", "amazon.titan", "anthropic.claude-3-5-sonnet",
                "us.anthropic.claude", "eu.anthropic.claude"
            ]
            should_skip_temp = any(model in model_lower for model in skip_temperature_models)

            if not should_skip_temp:
                kwargs["temperature"] = self._config.temperature

            if self._config.api_key:
                kwargs["api_key"] = self._config.api_key
            if self._config.api_base:
                # 使用 base_url 而不是 api_base（LiteLLM 的自定义端点参数）
                kwargs["base_url"] = self._config.api_base

            # 支持强制指定提供商（避免 LiteLLM 自动路由）
            if self._config.extra_params and "custom_llm_provider" in self._config.extra_params:
                kwargs["custom_llm_provider"] = self._config.extra_params["custom_llm_provider"]

            response = await litellm.acompletion(**kwargs)

            content = response.choices[0].message.content or ""
            total_tokens = response.usage.total_tokens if response.usage else 0

            # 调试日志：记录 LLM 原始响应
            logger.info("=== LLM 原始响应 ===")
            logger.info(f"Token 使用量: {total_tokens}")
            logger.info(f"响应内容（前500字符）: {content[:500]}")
            logger.info(f"响应长度: {len(content)} 字符")

            # 使用多格式解析器解析模型返回
            # 将配置的 response_format 字符串转换为 ResponseFormat 枚举
            try:
                format_hint = ResponseFormat(self._config.response_format or "auto")
            except ValueError:
                logger.warning(f"无效的响应格式配置: {self._config.response_format}，使用自动检测")
                format_hint = ResponseFormat.AUTO

            parsed_result: ParsedReview = self._parser.parse(content, format_hint=format_hint)
            comments = parsed_result.comments
            summary = parsed_result.summary

            # 记录解析详情
            logger.info(
                f"解析完成: 配置格式={self._config.response_format}, "
                f"实际使用格式={parsed_result.format_used.value}, "
                f"评论数={len(comments)}, "
                f"摘要长度={len(summary)}"
            )
            for warning in parsed_result.warnings:
                logger.warning(f"解析警告: {warning}")

        except ValueError as e:
            # 多格式解析失败
            logger.error("多格式解析器失败: %s", e)
            raise
        except Exception as e:
            # LLM 调用失败（网络错误、认证错误等），重新抛出异常
            logger.error("LLM review failed: %s", e)
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
