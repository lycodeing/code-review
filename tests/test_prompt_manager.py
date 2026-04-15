"""Prompt 模板管理器测试（数据库模式）。"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from code_review.infrastructure.prompt_manager import (
    PromptTemplateManager,
    EXTENSION_LANGUAGE_MAP,
)
from code_review.models.db import PromptTemplate


def _make_db_template(
    name: str = "default_zh",
    category: str = "default",
    locale: str = "zh",
    content: str = "builtin {{diff}} {{files_context}}",
    enabled: int = 1,
) -> PromptTemplate:
    return PromptTemplate(
        name=name, content=content, category=category, locale=locale, enabled=enabled,
    )


class TestPromptTemplateManager:
    """数据库模式模板管理器测试。"""

    def test_detect_language_python(self):
        manager = PromptTemplateManager()
        assert manager.detect_language("main.py") == "python"

    def test_detect_language_java(self):
        manager = PromptTemplateManager()
        assert manager.detect_language("App.java") == "java"

    def test_detect_language_typescript(self):
        manager = PromptTemplateManager()
        assert manager.detect_language("app.tsx") == "typescript"

    def test_detect_language_unknown(self):
        manager = PromptTemplateManager()
        assert manager.detect_language("Makefile") == "default"

    def test_builtin_fallback_contains_placeholders(self):
        manager = PromptTemplateManager(language="zh")
        fallback = manager._builtin_default_template()
        assert "{{diff}}" in fallback
        assert "{{files_context}}" in fallback

    @pytest.mark.asyncio
    async def test_get_template_by_name(self):
        """按名称精确查找。"""
        manager = PromptTemplateManager(language="zh")
        session = AsyncMock()

        mock_tpl = _make_db_template(name="my_custom", content="custom content")
        svc_mock = MagicMock()
        svc_mock.get_by_name = AsyncMock(return_value=mock_tpl)

        from unittest.mock import patch
        with patch(
            "code_review.infrastructure.prompt_manager.PromptTemplateService",
            return_value=svc_mock,
        ):
            result = await manager.get_template(session, template_name="my_custom")
            assert result == "custom content"
            svc_mock.get_by_name.assert_called_once_with("my_custom")

    @pytest.mark.asyncio
    async def test_get_template_by_name_disabled_falls_through(self):
        """按名称找到但已禁用，应继续按分类匹配。"""
        manager = PromptTemplateManager(language="zh")
        session = AsyncMock()

        disabled_tpl = _make_db_template(name="disabled", enabled=0)
        matched_tpl = _make_db_template(name="default_zh", content="matched")
        svc_mock = MagicMock()
        svc_mock.get_by_name = AsyncMock(return_value=disabled_tpl)
        svc_mock.find_best_match = AsyncMock(return_value=matched_tpl)

        from unittest.mock import patch
        with patch(
            "code_review.infrastructure.prompt_manager.PromptTemplateService",
            return_value=svc_mock,
        ):
            result = await manager.get_template(session, language="default")
            assert result == "matched"

    @pytest.mark.asyncio
    async def test_get_template_by_category_match(self):
        """按分类 + 语言自动匹配。"""
        manager = PromptTemplateManager(language="zh")
        session = AsyncMock()

        matched_tpl = _make_db_template(
            name="python_zh", category="python", locale="zh", content="python zh tpl"
        )
        svc_mock = MagicMock()
        svc_mock.get_by_name = AsyncMock(return_value=None)
        svc_mock.find_best_match = AsyncMock(return_value=matched_tpl)

        from unittest.mock import patch
        with patch(
            "code_review.infrastructure.prompt_manager.PromptTemplateService",
            return_value=svc_mock,
        ):
            result = await manager.get_template(session, language="python")
            assert result == "python zh tpl"
            svc_mock.find_best_match.assert_called_once_with("python", "zh")

    @pytest.mark.asyncio
    async def test_get_template_fallback_to_builtin(self):
        """数据库无匹配模板时回退到内置模板。"""
        manager = PromptTemplateManager(language="zh")
        session = AsyncMock()

        svc_mock = MagicMock()
        svc_mock.get_by_name = AsyncMock(return_value=None)
        svc_mock.find_best_match = AsyncMock(return_value=None)

        from unittest.mock import patch
        with patch(
            "code_review.infrastructure.prompt_manager.PromptTemplateService",
            return_value=svc_mock,
        ):
            result = await manager.get_template(session, language="nonexistent")
            assert "{{diff}}" in result
