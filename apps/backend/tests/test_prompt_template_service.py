"""Prompt 模板 CRUD 服务层测试。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from code_review.models.db import PromptTemplate
from code_review.services.prompt_template_service import (
    PromptTemplateService,
    seed_default_templates,
    BUILTIN_TEMPLATES,
)


def _make_template(**overrides) -> PromptTemplate:
    defaults = {
        "name": "test_template",
        "content": "review {{diff}}",
        "category": "default",
        "locale": "zh",
        "enabled": 1,
    }
    defaults.update(overrides)
    return PromptTemplate(**defaults)


class TestPromptTemplateService:
    """CRUD 操作测试。"""

    @pytest.mark.asyncio
    async def test_create(self):
        session = AsyncMock()
        svc = PromptTemplateService(session)
        tpl = await svc.create(name="new_tpl", content="hello {{diff}}", category="python")
        assert tpl.name == "new_tpl"
        assert tpl.content == "hello {{diff}}"
        assert tpl.category == "python"
        session.add.assert_called_once()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id(self):
        session = AsyncMock()
        tpl_id = uuid4()
        mock_tpl = _make_template(id=tpl_id)
        session.get = AsyncMock(return_value=mock_tpl)

        svc = PromptTemplateService(session)
        result = await svc.get_by_id(tpl_id)
        assert result is mock_tpl
        session.get.assert_called_once_with(PromptTemplate, tpl_id)

    @pytest.mark.asyncio
    async def test_get_by_name(self):
        session = AsyncMock()
        mock_tpl = _make_template(name="python_zh")
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = mock_tpl
        session.execute = AsyncMock(return_value=exec_result)

        svc = PromptTemplateService(session)
        result = await svc.get_by_name("python_zh")
        assert result is mock_tpl

    @pytest.mark.asyncio
    async def test_update(self):
        session = AsyncMock()
        tpl_id = uuid4()
        mock_tpl = _make_template(id=tpl_id)
        session.get = AsyncMock(return_value=mock_tpl)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        svc = PromptTemplateService(session)
        result = await svc.update(tpl_id, content="new content", enabled=0)
        assert result is mock_tpl
        assert mock_tpl.content == "new content"
        assert mock_tpl.enabled == 0

    @pytest.mark.asyncio
    async def test_update_not_found(self):
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)

        svc = PromptTemplateService(session)
        result = await svc.update(uuid4(), content="x")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self):
        session = AsyncMock()
        mock_tpl = _make_template()
        session.get = AsyncMock(return_value=mock_tpl)
        session.delete = AsyncMock()
        session.commit = AsyncMock()

        svc = PromptTemplateService(session)
        assert await svc.delete(mock_tpl.id) is True
        session.delete.assert_called_once_with(mock_tpl)

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)

        svc = PromptTemplateService(session)
        assert await svc.delete(uuid4()) is False

    @pytest.mark.asyncio
    async def test_list_templates(self):
        session = AsyncMock()
        # count query
        count_result = MagicMock()
        count_result.scalar.return_value = 2
        # list query
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = [
            _make_template(name="a"),
            _make_template(name="b"),
        ]
        session.execute = AsyncMock(side_effect=[count_result, list_result])

        svc = PromptTemplateService(session)
        items, total = await svc.list_templates(category="default")
        assert total == 2
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_list_with_filters(self):
        session = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = 1
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = [
            _make_template(name="python_zh", category="python", locale="zh"),
        ]
        session.execute = AsyncMock(side_effect=[count_result, list_result])

        svc = PromptTemplateService(session)
        items, total = await svc.list_templates(category="python", locale="zh")
        assert total == 1


class TestFindBestMatch:
    """模板匹配优先级测试。"""

    @pytest.mark.asyncio
    async def test_exact_match(self):
        """分类 + 语言精确匹配。"""
        session = AsyncMock()
        matched = _make_template(category="python", locale="zh")
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = matched
        session.execute = AsyncMock(return_value=exec_result)

        svc = PromptTemplateService(session)
        result = await svc.find_best_match("python", "zh")
        assert result is matched

    @pytest.mark.asyncio
    async def test_fallback_to_default_locale(self):
        """分类匹配但语言不匹配 → 回退到分类任意语言。"""
        session = AsyncMock()
        calls = [0]

        async def mock_execute(stmt):
            calls[0] += 1
            r = MagicMock()
            # 第一次调用（精确匹配）返回 None
            if calls[0] == 1:
                r.scalar_one_or_none.return_value = None
            else:
                r.scalar_one_or_none.return_value = _make_template(category="python", locale="en")
            return r

        session.execute = mock_execute
        svc = PromptTemplateService(session)
        result = await svc.find_best_match("python", "zh")
        assert result is not None
        assert calls[0] == 2  # 第二次才命中

    @pytest.mark.asyncio
    async def test_fallback_to_default_category(self):
        """无匹配 → 回退到 default 分类。"""
        session = AsyncMock()
        calls = [0]

        async def mock_execute(stmt):
            calls[0] += 1
            r = MagicMock()
            if calls[0] >= 3:
                r.scalar_one_or_none.return_value = _make_template(
                    category="default", locale="zh"
                )
            else:
                r.scalar_one_or_none.return_value = None
            return r

        session.execute = mock_execute
        svc = PromptTemplateService(session)
        result = await svc.find_best_match("nonexistent", "zh")
        assert result is not None

    @pytest.mark.asyncio
    async def test_no_match_returns_none(self):
        """全部无匹配返回 None。"""
        session = AsyncMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=exec_result)

        svc = PromptTemplateService(session)
        result = await svc.find_best_match("nonexistent", "xx")
        assert result is None


class TestSeedDefaultTemplates:
    """种子数据测试。"""

    @pytest.mark.asyncio
    async def test_seed_inserts_when_empty(self):
        session = AsyncMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=exec_result)
        session.commit = AsyncMock()

        await seed_default_templates(session)
        # 每个内置模板调用一次 add
        assert session.add.call_count == len(BUILTIN_TEMPLATES)
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_seed_skips_existing(self):
        session = AsyncMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = _make_template()
        session.execute = AsyncMock(return_value=exec_result)
        session.commit = AsyncMock()

        await seed_default_templates(session)
        session.add.assert_not_called()
