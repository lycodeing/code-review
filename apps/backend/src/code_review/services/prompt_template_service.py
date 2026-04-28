"""Prompt 模板 CRUD 服务层。

提供模板的数据库 CRUD 操作和启动时的默认数据种子。
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from code_review.models.db import PromptTemplate, ProjectPromptBinding

logger = logging.getLogger(__name__)


# ---- 内置默认模板（用于种子数据）----

BUILTIN_TEMPLATES: list[dict] = [
    {
        "name": "default_zh",
        "category": "default",
        "locale": "zh",
        "content": (
            "请对以下代码变更进行专业评审，返回 JSON 格式的评审意见。\n\n"
            "## 评审要求\n"
            "1. 仔细检查代码逻辑、安全性、性能和可维护性\n"
            "2. 识别潜在的 Bug、安全漏洞和性能问题\n"
            "3. 给出具体的改进建议\n"
            "4. 严重程度分级：critical（必须修复）、warning（建议修复）、suggestion（优化建议）、info（信息提示）\n\n"
            "## 变更文件\n{{files_context}}\n\n"
            "## Diff 内容\n```\n{{diff}}\n```\n\n"
            "## 输出格式\n请严格按照以下 JSON 格式输出：\n"
            "```json\n{\n"
            '    "summary": "整体评审摘要（2-3句话总结主要发现）",\n'
            '    "comments": [\n        {\n'
            '            "file_path": "文件路径",\n'
            '            "line_start": 起始行号,\n'
            '            "line_end": 结束行号,\n'
            '            "severity": "critical|warning|suggestion|info",\n'
            '            "message": "评审意见（中文）",\n'
            '            "suggestion": "具体的修复建议或代码示例"\n'
            "        }\n    ]\n}\n```"
        ),
    },
    {
        "name": "default_en",
        "category": "default",
        "locale": "en",
        "content": (
            "Please review the following code changes and return structured feedback in JSON format.\n\n"
            "## Review Guidelines\n"
            "1. Check code logic, security, performance, and maintainability\n"
            "2. Identify potential bugs, security vulnerabilities, and performance issues\n"
            "3. Provide specific improvement suggestions\n"
            "4. Severity levels: critical (must fix), warning (should fix), suggestion (nice to have), info (informational)\n\n"
            "## Changed Files\n{{files_context}}\n\n"
            "## Diff\n```\n{{diff}}\n```\n\n"
            "## Output Format\nReturn strictly in this JSON format:\n"
            "```json\n{\n"
            '    "summary": "Overall review summary (2-3 sentences)",\n'
            '    "comments": [\n        {\n'
            '            "file_path": "file path",\n'
            '            "line_start": start_line,\n'
            '            "line_end": end_line,\n'
            '            "severity": "critical|warning|suggestion|info",\n'
            '            "message": "review comment",\n'
            '            "suggestion": "specific fix suggestion or code example"\n'
            "        }\n    ]\n}\n```"
        ),
    },
    {
        "name": "python_zh",
        "category": "python",
        "locale": "zh",
        "content": (
            "请对以下 Python 代码变更进行专业评审，返回 JSON 格式的评审意见。\n\n"
            "## 评审要求\n"
            "1. 检查 Python 特有问题：类型安全、异常处理、资源管理\n"
            "2. 关注安全漏洞：注入攻击、不安全的反序列化、路径遍历\n"
            "3. 审查代码风格（PEP 8）、docstring、类型提示\n"
            "4. 检查性能问题：不必要的计算、N+1 查询、内存泄漏\n"
            "5. 严重程度：critical（必须修复）、warning（建议修复）、suggestion（优化）、info（信息）\n\n"
            "## 变更文件\n{{files_context}}\n\n"
            "## Diff 内容\n```\n{{diff}}\n```\n\n"
            "## 输出格式\n```json\n{\n"
            '    "summary": "整体评审摘要（2-3句话总结主要发现）",\n'
            '    "comments": [\n        {\n'
            '            "file_path": "文件路径",\n'
            '            "line_start": 起始行号,\n'
            '            "line_end": 结束行号,\n'
            '            "severity": "critical|warning|suggestion|info",\n'
            '            "message": "评审意见",\n'
            '            "suggestion": "修复建议或代码示例"\n'
            "        }\n    ]\n}\n```"
        ),
    },
    {
        "name": "java_zh",
        "category": "java",
        "locale": "zh",
        "content": (
            "请对以下 Java 代码变更进行专业评审，返回 JSON 格式的评审意见。\n\n"
            "## 评审要求\n"
            "1. 检查 Java 最佳实践：SOLID 原则、设计模式、异常处理\n"
            "2. 关注线程安全、资源泄漏（连接/流未关闭）\n"
            "3. 检查空指针风险、空集合处理\n"
            "4. 审查日志规范、方法复杂度、命名规范\n"
            "5. 严重程度：critical（必须修复）、warning（建议修复）、suggestion（优化）、info（信息）\n\n"
            "## 变更文件\n{{files_context}}\n\n"
            "## Diff 内容\n```\n{{diff}}\n```\n\n"
            "## 输出格式\n```json\n{\n"
            '    "summary": "整体评审摘要",\n'
            '    "comments": [\n        {\n'
            '            "file_path": "文件路径",\n'
            '            "line_start": 起始行号,\n'
            '            "line_end": 结束行号,\n'
            '            "severity": "critical|warning|suggestion|info",\n'
            '            "message": "评审意见",\n'
            '            "suggestion": "修复建议或代码示例"\n'
            "        }\n    ]\n}\n```"
        ),
    },
]


async def seed_default_templates(session: AsyncSession) -> None:
    """启动时向数据库插入默认模板（已存在则跳过）。

    幂等操作：按 name 唯一约束去重。
    """
    for tpl_data in BUILTIN_TEMPLATES:
        existing = await session.execute(
            select(PromptTemplate).where(PromptTemplate.name == tpl_data["name"])
        )
        if existing.scalar_one_or_none() is not None:
            continue
        tpl = PromptTemplate(
            name=tpl_data["name"],
            content=tpl_data["content"],
            category=tpl_data["category"],
            locale=tpl_data["locale"],
            enabled=1,
        )
        session.add(tpl)
        logger.info("Seeded prompt template: %s", tpl_data["name"])

    await session.commit()


class PromptTemplateService:
    """Prompt 模板 CRUD 服务。"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(
        self,
        name: str,
        content: str,
        category: str = "default",
        locale: str = "zh",
    ) -> PromptTemplate:
        """创建模板。"""
        tpl = PromptTemplate(
            name=name,
            content=content,
            category=category,
            locale=locale,
            enabled=1,
        )
        self._session.add(tpl)
        await self._session.commit()
        await self._session.refresh(tpl)
        return tpl

    async def get_by_id(self, template_id: UUID) -> PromptTemplate | None:
        """根据 ID 查询。"""
        return await self._session.get(PromptTemplate, template_id)

    async def get_by_name(self, name: str) -> PromptTemplate | None:
        """根据名称查询。"""
        stmt = select(PromptTemplate).where(PromptTemplate.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_templates(
        self,
        category: str | None = None,
        locale: str | None = None,
        enabled: int | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[PromptTemplate], int]:
        """按条件筛选模板列表，返回 (列表, 总数)。"""
        conditions = []
        if category is not None:
            conditions.append(PromptTemplate.category == category)
        if locale is not None:
            conditions.append(PromptTemplate.locale == locale)
        if enabled is not None:
            conditions.append(PromptTemplate.enabled == enabled)

        # 总数
        count_stmt = select(func.count()).select_from(PromptTemplate)
        if conditions:
            count_stmt = count_stmt.where(*conditions)
        total = (await self._session.execute(count_stmt)).scalar() or 0

        # 列表
        list_stmt = (
            select(PromptTemplate)
            .order_by(PromptTemplate.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if conditions:
            list_stmt = list_stmt.where(*conditions)
        result = await self._session.execute(list_stmt)
        return result.scalars().all(), total

    async def update(
        self,
        template_id: UUID,
        *,
        name: str | None = None,
        content: str | None = None,
        category: str | None = None,
        locale: str | None = None,
        enabled: int | None = None,
    ) -> PromptTemplate | None:
        """更新模板字段。"""
        tpl = await self._session.get(PromptTemplate, template_id)
        if tpl is None:
            return None
        if name is not None:
            tpl.name = name
        if content is not None:
            tpl.content = content
        if category is not None:
            tpl.category = category
        if locale is not None:
            tpl.locale = locale
        if enabled is not None:
            tpl.enabled = enabled
        tpl.updated_at = datetime.now(timezone.utc)
        await self._session.commit()
        await self._session.refresh(tpl)
        return tpl

    async def delete(self, template_id: UUID) -> bool:
        """删除模板，返回是否成功。"""
        tpl = await self._session.get(PromptTemplate, template_id)
        if tpl is None:
            return False
        await self._session.delete(tpl)
        await self._session.commit()
        return True

    async def find_best_match(
        self, category: str, locale: str
    ) -> PromptTemplate | None:
        """按分类和语言查找最佳匹配模板。

        查找优先级：
        1. category + locale 精确匹配
        2. category + 任意 locale
        3. default + locale 匹配
        4. default + 任意 locale
        """
        for cat, loc in [
            (category, locale),
            (category, None),
            ("default", locale),
            ("default", None),
        ]:
            conditions = [
                PromptTemplate.category == cat,
                PromptTemplate.enabled == 1,
            ]
            if loc is not None:
                conditions.append(PromptTemplate.locale == loc)
            stmt = select(PromptTemplate).where(*conditions).limit(1)
            result = await self._session.execute(stmt)
            tpl = result.scalar_one_or_none()
            if tpl is not None:
                return tpl
        return None

    # ========== 项目绑定管理 ==========

    async def list_bindings(self, project_id) -> list[ProjectPromptBinding]:
        """列出项目的 Prompt 模板绑定。"""
        from uuid import UUID
        if isinstance(project_id, str):
            project_id = UUID(project_id)

        stmt = (
            select(ProjectPromptBinding)
            .where(ProjectPromptBinding.project_id == project_id)
            .order_by(ProjectPromptBinding.priority.desc(), ProjectPromptBinding.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_binding(self, binding_id) -> ProjectPromptBinding | None:
        """获取绑定详情。"""
        from uuid import UUID
        if isinstance(binding_id, str):
            binding_id = UUID(binding_id)
        return await self._session.get(ProjectPromptBinding, binding_id)

    async def create_binding(
        self,
        project_id,
        template_id,
        is_default: bool = False,
        priority: int = 0,
    ) -> ProjectPromptBinding:
        """创建项目-Prompt 模板绑定。"""
        from uuid import UUID
        if isinstance(project_id, str):
            project_id = UUID(project_id)
        if isinstance(template_id, str):
            template_id = UUID(template_id)

        # 检查模板是否存在
        tpl = await self._session.get(PromptTemplate, template_id)
        if not tpl:
            raise ValueError(f"模板 {template_id} 不存在")

        # 如果设置为默认，清除其他默认标记
        if is_default:
            stmt = select(ProjectPromptBinding).where(
                ProjectPromptBinding.project_id == project_id,
                ProjectPromptBinding.is_default == True,
            )
            result = await self._session.execute(stmt)
            for binding in result.scalars().all():
                binding.is_default = False

        binding = ProjectPromptBinding(
            project_id=project_id,
            template_id=template_id,
            is_default=is_default,
            priority=priority,
        )
        self._session.add(binding)
        await self._session.commit()
        await self._session.refresh(binding)
        return binding

    async def update_binding(
        self,
        binding_id,
        is_default: bool | None = None,
        priority: int | None = None,
        enabled: bool | None = None,
    ) -> ProjectPromptBinding:
        """更新绑定。"""
        from uuid import UUID
        if isinstance(binding_id, str):
            binding_id = UUID(binding_id)

        binding = await self._session.get(ProjectPromptBinding, binding_id)
        if not binding:
            raise ValueError(f"绑定 {binding_id} 不存在")

        if is_default is not None:
            if is_default:
                stmt = select(ProjectPromptBinding).where(
                    ProjectPromptBinding.project_id == binding.project_id,
                    ProjectPromptBinding.is_default == True,
                    ProjectPromptBinding.id != binding_id,
                )
                result = await self._session.execute(stmt)
                for b in result.scalars().all():
                    b.is_default = False
            binding.is_default = is_default

        if priority is not None:
            binding.priority = priority
        if enabled is not None:
            binding.enabled = enabled

        await self._session.commit()
        await self._session.refresh(binding)
        return binding

    async def delete_binding(self, binding_id) -> None:
        """删除绑定。"""
        from uuid import UUID
        if isinstance(binding_id, str):
            binding_id = UUID(binding_id)

        binding = await self._session.get(ProjectPromptBinding, binding_id)
        if not binding:
            raise ValueError(f"绑定 {binding_id} 不存在")
        await self._session.delete(binding)

    async def set_default_binding(self, binding_id) -> ProjectPromptBinding:
        """设置默认绑定。"""
        from uuid import UUID
        if isinstance(binding_id, str):
            binding_id = UUID(binding_id)

        binding = await self._session.get(ProjectPromptBinding, binding_id)
        if not binding:
            raise ValueError(f"绑定 {binding_id} 不存在")

        # 清除同项目其他默认标记
        stmt = select(ProjectPromptBinding).where(
            ProjectPromptBinding.project_id == binding.project_id,
            ProjectPromptBinding.is_default == True,
            ProjectPromptBinding.id != binding_id,
        )
        result = await self._session.execute(stmt)
        for b in result.scalars().all():
            b.is_default = False

        binding.is_default = True
        await self._session.commit()
        await self._session.refresh(binding)
        return binding

    async def get_template_for_project(self, project_id) -> PromptTemplate | None:
        """获取项目的 Prompt 模板。

        选择优先级：
        1. 项目的默认绑定（is_default=True）
        2. 项目的最高优先级绑定（priority DESC）
        3. None（返回 None，由调用方按分类自动匹配）
        """
        from uuid import UUID
        if isinstance(project_id, str):
            project_id = UUID(project_id)

        # 1. 查找项目默认绑定
        stmt = (
            select(PromptTemplate)
            .join(ProjectPromptBinding)
            .where(
                ProjectPromptBinding.project_id == project_id,
                ProjectPromptBinding.is_default == True,
                ProjectPromptBinding.enabled == True,
                PromptTemplate.enabled == 1,
            )
        )
        result = await self._session.execute(stmt)
        tpl = result.scalar_one_or_none()
        if tpl:
            return tpl

        # 2. 查找项目最高优先级绑定
        stmt = (
            select(PromptTemplate)
            .join(ProjectPromptBinding)
            .where(
                ProjectPromptBinding.project_id == project_id,
                ProjectPromptBinding.enabled == True,
                PromptTemplate.enabled == 1,
            )
            .order_by(ProjectPromptBinding.priority.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        tpl = result.scalar_one_or_none()
        if tpl:
            return tpl

        return None
