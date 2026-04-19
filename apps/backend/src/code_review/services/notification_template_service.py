"""通知模板 CRUD 服务层。

提供模板的数据库 CRUD 操作、默认模板查询，以及三级优先级模板解析逻辑。
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from code_review.models.db import (
    NotificationConfig,
    NotificationTemplate,
    ProjectNotificationTemplateBinding,
)

logger = logging.getLogger(__name__)


class NotificationTemplateService:
    """通知模板 CRUD 及模板解析服务。"""

    def __init__(self, session: AsyncSession):
        self._session = session

    # ========== 模板 CRUD ==========

    async def get_all(self, channel: str | None = None) -> list[NotificationTemplate]:
        """查询所有模板，可按渠道过滤。"""
        stmt = select(NotificationTemplate).order_by(
            NotificationTemplate.is_default.desc(),
            NotificationTemplate.created_at.asc(),
        )
        if channel is not None:
            stmt = stmt.where(NotificationTemplate.channel == channel)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, template_id: UUID) -> NotificationTemplate | None:
        """根据 ID 查询模板。"""
        return await self._session.get(NotificationTemplate, template_id)

    async def create(
        self,
        name: str,
        channel: str,
        title_template: str,
        body_template: str,
        description: str = "",
        enabled: bool = True,
    ) -> NotificationTemplate:
        """创建新模板（is_default 固定为 False，内置模板由迁移脚本写入）。"""
        tpl = NotificationTemplate(
            name=name,
            channel=channel,
            title_template=title_template,
            body_template=body_template,
            description=description,
            enabled=enabled,
            is_default=False,
        )
        self._session.add(tpl)
        await self._session.commit()
        await self._session.refresh(tpl)
        return tpl

    async def update(
        self,
        template_id: UUID,
        *,
        name: str | None = None,
        title_template: str | None = None,
        body_template: str | None = None,
        description: str | None = None,
        enabled: bool | None = None,
    ) -> NotificationTemplate | None:
        """更新模板字段（is_default 不允许通过此接口修改）。"""
        tpl = await self._session.get(NotificationTemplate, template_id)
        if tpl is None:
            return None
        if name is not None:
            tpl.name = name
        if title_template is not None:
            tpl.title_template = title_template
        if body_template is not None:
            tpl.body_template = body_template
        if description is not None:
            tpl.description = description
        if enabled is not None:
            tpl.enabled = enabled
        tpl.updated_at = datetime.now(tz=timezone.utc)
        await self._session.commit()
        await self._session.refresh(tpl)
        return tpl

    async def delete(self, template_id: UUID) -> bool:
        """删除模板，is_default=True 的内置模板不可删除，返回是否成功。"""
        tpl = await self._session.get(NotificationTemplate, template_id)
        if tpl is None:
            return False
        if tpl.is_default:
            raise ValueError(f"内置默认模板 '{tpl.name}' 不可删除")
        await self._session.delete(tpl)
        await self._session.commit()
        return True

    # ========== 默认模板查询 ==========

    async def get_default(self, channel: str) -> NotificationTemplate | None:
        """获取指定渠道的内置默认模板（is_default=True）。"""
        stmt = (
            select(NotificationTemplate)
            .where(
                NotificationTemplate.channel == channel,
                NotificationTemplate.is_default == True,  # noqa: E712
                NotificationTemplate.enabled == True,  # noqa: E712
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    # ========== 三级优先级模板解析 ==========

    async def resolve_template(
        self,
        project_id: UUID,
        notification_id: UUID,
    ) -> NotificationTemplate | None:
        """解析模板：仅使用数据库中用户显式配置的绑定。

        优先级（从高到低）：
        1. project_notification_template_bindings（项目 + 渠道 → 模板）
        2. notification_configs.template_id（渠道级默认模板）

        两级均未配置时返回 None，由调用方决定是否报错。
        """
        # --- 第一优先级：项目级绑定 ---
        stmt = (
            select(ProjectNotificationTemplateBinding)
            .where(
                ProjectNotificationTemplateBinding.project_id == project_id,
                ProjectNotificationTemplateBinding.notification_id == notification_id,
                ProjectNotificationTemplateBinding.enabled == True,  # noqa: E712
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        binding = result.scalar_one_or_none()
        if binding is not None and binding.template_id is not None:
            tpl = await self._session.get(NotificationTemplate, binding.template_id)
            if tpl is not None and tpl.enabled:
                logger.info("使用项目级绑定模板: %s", tpl.name)
                return tpl

        # --- 第二优先级：渠道级默认模板 ---
        nc = await self._session.get(NotificationConfig, notification_id)
        if nc is not None and nc.template_id is not None:
            tpl = await self._session.get(NotificationTemplate, nc.template_id)
            if tpl is not None and tpl.enabled:
                logger.info("使用渠道级默认模板: %s", tpl.name)
                return tpl

        return None

    # ========== 项目级绑定管理 ==========

    async def get_project_bindings(
        self, project_id: UUID
    ) -> list[ProjectNotificationTemplateBinding]:
        """查询项目的所有通知模板绑定，同时 JOIN 渠道和模板信息以便序列化。"""
        stmt = (
            select(ProjectNotificationTemplateBinding)
            .where(ProjectNotificationTemplateBinding.project_id == project_id)
            .order_by(ProjectNotificationTemplateBinding.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_project_bindings(
        self,
        project_id: UUID,
        bindings: list[dict],
    ) -> list[ProjectNotificationTemplateBinding]:
        """批量创建或更新项目的通知模板绑定。

        Args:
            project_id: 项目 UUID。
            bindings: 绑定列表，每项为 dict，包含
                      notification_id (str|UUID)、template_id (str|UUID|None)、enabled (bool)。

        Returns:
            更新后的绑定对象列表。
        """
        upserted: list[ProjectNotificationTemplateBinding] = []

        for item in bindings:
            notification_id = item["notification_id"]
            if isinstance(notification_id, str):
                notification_id = UUID(notification_id)

            template_id = item.get("template_id")
            if isinstance(template_id, str) and template_id:
                template_id = UUID(template_id)
            elif not template_id:
                template_id = None

            enabled = bool(item.get("enabled", True))

            # 查找已有绑定
            stmt = select(ProjectNotificationTemplateBinding).where(
                ProjectNotificationTemplateBinding.project_id == project_id,
                ProjectNotificationTemplateBinding.notification_id == notification_id,
            )
            result = await self._session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing is not None:
                existing.template_id = template_id
                existing.enabled = enabled
                upserted.append(existing)
            else:
                new_binding = ProjectNotificationTemplateBinding(
                    project_id=project_id,
                    notification_id=notification_id,
                    template_id=template_id,
                    enabled=enabled,
                )
                self._session.add(new_binding)
                upserted.append(new_binding)

        await self._session.commit()

        # 刷新所有对象以获取数据库生成的字段
        for b in upserted:
            await self._session.refresh(b)

        return upserted

    # ========== 渠道默认模板设置 ==========

    async def set_channel_default_template(
        self,
        channel: str,
        template_id: UUID | None,
    ) -> NotificationConfig | None:
        """设置渠道的默认模板（可传 None 以清除）。

        Args:
            channel: 渠道标识（dingtalk/feishu）。
            template_id: 模板 UUID，None 表示清除渠道默认模板绑定。

        Returns:
            更新后的 NotificationConfig，若渠道不存在则返回 None。
        """
        stmt = select(NotificationConfig).where(NotificationConfig.channel == channel)
        result = await self._session.execute(stmt)
        nc = result.scalar_one_or_none()
        if nc is None:
            return None

        # 验证模板存在（非 None 时）
        if template_id is not None:
            tpl = await self._session.get(NotificationTemplate, template_id)
            if tpl is None:
                raise ValueError(f"模板 {template_id} 不存在")
            if tpl.channel != channel:
                raise ValueError(
                    f"模板渠道 '{tpl.channel}' 与目标渠道 '{channel}' 不匹配"
                )

        nc.template_id = template_id
        nc.updated_at = datetime.now(tz=timezone.utc)
        await self._session.commit()
        await self._session.refresh(nc)
        return nc
