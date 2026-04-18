"""基于 LangChain 的大模型评审器实现。"""

import logging
import time
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI

from code_review.core.llm import LLMReviewer, ReviewComment, ReviewResult
from code_review.core.platform import FileChange
from code_review.infrastructure.response_parser import (
    MultiFormatResponseParser,
    ParsedReview,
    ResponseFormat,
)
from code_review.models.config import LLMConfig

logger = logging.getLogger(__name__)


class LangChainReviewer(LLMReviewer):
    """使用 LangChain 的大模型评审器。

    支持所有 OpenAI 兼容的 API，只需修改 base_url 即可切换提供商：
    - OpenAI (GPT-4/GPT-3.5)
    - Geneasy MaaS (Claude Opus 4.7)
    - 智谱 AI (GLM)
    - DeepSeek
    - 通义千问
    - 本地模型 (Ollama)
    """

    def __init__(self, config: LLMConfig):
        self._config = config
        self._parser = MultiFormatResponseParser()
        self._llm = self._create_llm()

    def _create_llm(self) -> ChatOpenAI:
        """创建 LangChain LLM 实例（非流式）。"""
        if not self._config.api_key:
            raise ValueError("LLM API Key 未配置，请检查 LLMConfig.api_key")

        kwargs = {
            "model": self._config.model,
            "api_key": self._config.api_key,
            "max_tokens": self._config.max_tokens,
            "timeout": self._config.timeout,
            "streaming": False,  # 显式禁用流式模式，确保一次性返回完整响应
        }

        # 处理 temperature 参数
        # Claude 某些版本不支持 temperature，自动检测
        model_lower = self._config.model.lower()
        skip_temperature = "claude" in model_lower

        # 检查 extra_params 中的设置
        if self._config.extra_params:
            temp_value = self._config.extra_params.get("temperature", "__NOT_SET__")
            if temp_value == "__NOT_SET__":
                # extra_params 中没有指定 temperature
                if not skip_temperature:
                    kwargs["temperature"] = self._config.temperature
            elif temp_value is None:
                # 明确设置为 null，不传 temperature 参数
                skip_temperature = True
            else:
                # 使用 extra_params 中指定的值
                kwargs["temperature"] = temp_value
                skip_temperature = False
        else:
            # 没有 extra_params
            if not skip_temperature:
                kwargs["temperature"] = self._config.temperature

        # 如果有自定义 base_url，使用它
        if self._config.api_base:
            kwargs["base_url"] = self._config.api_base

        logger.debug(
            "创建 LangChain LLM: model=%s, base_url=%s, temperature=%s",
            self._config.model,
            self._config.api_base,
            'off' if skip_temperature else kwargs.get('temperature', 'N/A'),
        )

        return ChatOpenAI(**kwargs)

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
            # 构建消息
            messages = [
                SystemMessage(content=(
                    "You are an expert code reviewer. "
                    "Analyze the provided diff and return structured review comments. "
                    "Always respond in valid JSON format."
                )),
                HumanMessage(content=full_prompt),
            ]

            # 调用 LLM
            logger.debug("调用 LangChain LLM: model=%s, base_url=%s", self._config.model, self._config.api_base)

            response = await self._llm.ainvoke(messages)
            content = response.content

            # 尝试获取 token 使用量（LangChain 可能不返回）
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                total_tokens = response.usage_metadata.get('total_tokens', 0)
                logger.debug("Token 使用量: %d", total_tokens)

            logger.debug("响应长度: %d 字符", len(content))
            logger.debug("LLM 原始响应（前500字符）: %s", content[:500])

            # 使用多格式解析器解析模型返回
            try:
                format_hint = ResponseFormat(self._config.response_format or "auto")
            except ValueError:
                logger.warning(f"无效的响应格式配置: {self._config.response_format}，使用自动检测")
                format_hint = ResponseFormat.AUTO

            parsed_result: ParsedReview = self._parser.parse(content, format_hint=format_hint)
            comments = parsed_result.comments
            summary = parsed_result.summary

            # 记录解析详情
            logger.debug(
                "解析完成: 配置格式=%s, 实际使用格式=%s, 评论数=%d, 摘要长度=%d",
                self._config.response_format,
                parsed_result.format_used.value,
                len(comments),
                len(summary),
            )
            for warning in parsed_result.warnings:
                logger.warning(f"解析警告: {warning}")

        except ValueError as e:
            # 多格式解析失败
            logger.error("多格式解析器失败: %s", e)
            raise
        except Exception as e:
            logger.error(f"LangChain LLM 调用失败: {e}", exc_info=True)
            raise

        elapsed = time.time() - start_time
        logger.info(f"评审完成，耗时: {elapsed:.2f}秒")

        return ReviewResult(
            model=self._config.model,
            comments=comments,
            summary=summary,
            total_tokens=total_tokens,
            elapsed_seconds=elapsed,
        )

    async def health_check(self) -> bool:
        """检查 LLM 服务是否可用。"""
        try:
            # 发送一个简单的测试请求
            messages = [HumanMessage(content="Hello")]
            response = await self._llm.ainvoke(messages)
            return response is not None
        except Exception as e:
            logger.warning(f"LLM 健康检查失败: {e}")
            return False

    def _build_files_context(self, files: list[FileChange]) -> str:
        """构建文件上下文信息。"""
        if not files:
            return "（无文件变更）"

        parts = []
        for f in files:
            # 如果是重命名文件，显示旧路径 → 新路径
            if f.status == "renamed" and f.old_path and f.old_path != f.path:
                part = f"- `{f.old_path}` → `{f.path}`"
            else:
                part = f"- `{f.path}`"
            parts.append(part)

        return "\n".join(parts)
