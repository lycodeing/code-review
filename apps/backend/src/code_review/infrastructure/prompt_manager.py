"""Prompt 模板管理。

从数据库动态加载 Prompt 模板，支持热更新（无需重启）。
保留文件扩展名到编程语言的映射和 detect_language 能力。
"""

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from code_review.services.prompt_template_service import (
    PromptTemplateService,
    BUILTIN_TEMPLATES,
)

logger = logging.getLogger(__name__)

# 文件扩展名到编程语言的映射
EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sql": "sql",
    ".sh": "shell",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".xml": "xml",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".less": "less",
    ".dockerfile": "dockerfile",
    ".tf": "terraform",
    ".proto": "protobuf",
}


class PromptTemplateManager:
    """基于数据库的 Prompt 模板管理器。

    每次调用 get_template 时从数据库实时查询，天然支持热更新。
    如果数据库中没有匹配的模板，回退到内置默认模板。
    """

    def __init__(self, language: str = "zh"):
        self._language = language

    async def get_template(
        self,
        session: AsyncSession,
        language: str | None = None,
        template_name: str | None = None,
    ) -> str:
        """从数据库获取评审 prompt 模板。

        Args:
            session: 数据库会话。
            language: 编程语言分类（如 python/java）。None 时使用 default。
            template_name: 指定模板名称（优先级最高）。

        Returns:
            模板文本，包含 {{diff}} 和 {{files_context}} 占位符。
        """
        svc = PromptTemplateService(session)
        locale = self._language
        category = language or "default"

        # 优先级 1：按名称精确查找
        if template_name:
            tpl = await svc.get_by_name(template_name)
            if tpl and tpl.enabled:
                logger.debug("Loaded prompt template by name: %s", template_name)
                return tpl.content

        # 优先级 2：按分类 + 语言匹配
        tpl = await svc.find_best_match(category, locale)
        if tpl:
            logger.debug(
                "Loaded prompt template: %s (category=%s, locale=%s)",
                tpl.name, tpl.category, tpl.locale,
            )
            return tpl.content

        # 回退：内置默认模板
        logger.warning(
            "No matching template in DB for category=%s locale=%s, using builtin fallback",
            category, locale,
        )
        return self._builtin_default_template()

    def detect_language(self, file_path: str) -> str:
        """根据文件扩展名检测编程语言。"""
        suffix = Path(file_path).suffix.lower()
        return EXTENSION_LANGUAGE_MAP.get(suffix, "default")

    def _builtin_default_template(self) -> str:
        """内置的默认评审 prompt 模板（数据库无数据时的兜底）。"""
        for tpl in BUILTIN_TEMPLATES:
            if tpl["category"] == "default" and tpl["locale"] == self._language:
                return tpl["content"]
        # 最终兜底：取第一个内置模板
        return BUILTIN_TEMPLATES[0]["content"]
