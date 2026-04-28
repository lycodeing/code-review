"""LLM 配置服务。"""

import logging
from uuid import UUID
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from code_review.models.db import LLMConfig, ProjectLLMBinding
from code_review.infrastructure.config_crypto import encrypt, decrypt

logger = logging.getLogger(__name__)


class LLMConfigService:
    """LLM 配置服务。"""

    def __init__(self, session: AsyncSession, secret_key: str):
        """初始化服务。

        Args:
            session: 数据库会话
            secret_key: 加密密钥（从 SERVER__SECRET_KEY 派生）
        """
        self._session = session
        self._secret_key = secret_key

    async def list_configs(
        self, enabled_only: bool = False
    ) -> list[LLMConfig]:
        """列出所有 LLM 配置。

        Args:
            enabled_only: 是否只返回启用的配置

        Returns:
            LLM 配置列表
        """
        stmt = select(LLMConfig)
        if enabled_only:
            stmt = stmt.where(LLMConfig.enabled.is_(True))
        stmt = stmt.order_by(LLMConfig.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_config(self, config_id: UUID) -> Optional[LLMConfig]:
        """获取指定 LLM 配置。

        Args:
            config_id: 配置 ID

        Returns:
            LLM 配置或 None
        """
        return await self._session.get(LLMConfig, config_id)

    async def get_config_by_name(self, name: str) -> Optional[LLMConfig]:
        """根据名称获取 LLM 配置。

        Args:
            name: 配置名称

        Returns:
            LLM 配置或 None
        """
        stmt = select(LLMConfig).where(LLMConfig.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_config(
        self,
        name: str,
        provider: str,
        model_name: str,
        api_key: str,
        api_base: str = "",
        extra_params: Optional[dict] = None,
        response_format: str = "auto",
        enabled: bool = True,
        description: str = "",
    ) -> LLMConfig:
        """创建 LLM 配置。

        Args:
            name: 配置名称
            provider: 提供商
            model_name: 模型名称
            api_key: API 密钥
            api_base: API 基础地址
            extra_params: 额外参数
            response_format: 响应格式
            enabled: 是否启用
            description: 描述

        Returns:
            创建的 LLM 配置
        """
        # 检查名称唯一性
        existing = await self.get_config_by_name(name)
        if existing:
            raise ValueError(f"配置名称 '{name}' 已存在")

        # 加密 API Key
        encrypted_key = encrypt(api_key, self._secret_key)

        config = LLMConfig(
            name=name,
            provider=provider,
            model_name=model_name,
            api_key=encrypted_key,
            api_base=api_base,
            extra_params=extra_params,
            response_format=response_format,
            enabled=enabled,
            description=description,
        )
        self._session.add(config)
        await self._session.commit()
        await self._session.refresh(config)
        return config

    async def update_config(
        self,
        config_id: UUID,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        extra_params: Optional[dict] = None,
        response_format: Optional[str] = None,
        enabled: Optional[bool] = None,
        description: Optional[str] = None,
    ) -> LLMConfig:
        """更新 LLM 配置。

        Args:
            config_id: 配置 ID
            provider: 提供商（可选）
            model_name: 模型名称（可选）
            api_key: API 密钥（可选，传入 "********" 则保留原值）
            api_base: API 基础地址（可选）
            extra_params: 额外参数（可选）
            response_format: 响应格式（可选）
            enabled: 是否启用（可选）
            description: 描述（可选）

        Returns:
            更新后的 LLM 配置
        """
        config = await self.get_config(config_id)
        if not config:
            raise ValueError(f"配置 {config_id} 不存在")

        if provider is not None:
            config.provider = provider
        if model_name is not None:
            config.model_name = model_name
        if api_key is not None:
            # 如果传入的是脱敏值，则保留原值
            if api_key != "********":
                config.api_key = encrypt(api_key, self._secret_key)
        if api_base is not None:
            config.api_base = api_base
        if extra_params is not None:
            config.extra_params = extra_params
        if response_format is not None:
            config.response_format = response_format
        if enabled is not None:
            config.enabled = enabled
        if description is not None:
            config.description = description

        await self._session.commit()
        await self._session.refresh(config)
        return config

    async def delete_config(self, config_id: UUID) -> None:
        """删除 LLM 配置。

        Args:
            config_id: 配置 ID
        """
        config = await self.get_config(config_id)
        if not config:
            raise ValueError(f"配置 {config_id} 不存在")
        await self._session.delete(config)

    async def get_llm_config_for_project(
        self, project_id: UUID
    ) -> Optional[LLMConfig]:
        """获取项目的 LLM 配置。

        选择优先级：
        1. 项目的默认绑定（is_default=True）
        2. 项目的最高优先级绑定（priority DESC）
        3. None（返回 None，由调用方降级到环境变量）

        Args:
            project_id: 项目 ID

        Returns:
            LLM 配置或 None
        """
        # 1. 查找项目默认绑定
        stmt = (
            select(LLMConfig)
            .join(ProjectLLMBinding)
            .where(
                ProjectLLMBinding.project_id == project_id,
                ProjectLLMBinding.is_default.is_(True),
                ProjectLLMBinding.enabled.is_(True),
                LLMConfig.enabled.is_(True),
            )
        )
        result = await self._session.execute(stmt)
        config = result.scalar_one_or_none()
        if config:
            return config

        # 2. 查找项目最高优先级绑定
        stmt = (
            select(LLMConfig)
            .join(ProjectLLMBinding)
            .where(
                ProjectLLMBinding.project_id == project_id,
                ProjectLLMBinding.enabled.is_(True),
                LLMConfig.enabled.is_(True),
            )
            .order_by(ProjectLLMBinding.priority.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        config = result.scalar_one_or_none()
        if config:
            return config

        # 3. 没有找到配置，返回 None（调用方将降级到环境变量）
        return None

    async def decrypt_api_key(self, encrypted_key: str) -> str:
        """解密 API Key。

        Args:
            encrypted_key: 加密的 API Key

        Returns:
            解密后的 API Key
        """
        return decrypt(encrypted_key, self._secret_key)

    # ========== 绑定管理 ==========

    async def list_bindings(self, project_id: UUID) -> list[ProjectLLMBinding]:
        """列出项目的 LLM 绑定。

        Args:
            project_id: 项目 ID

        Returns:
            绑定列表
        """
        stmt = (
            select(ProjectLLMBinding)
            .where(ProjectLLMBinding.project_id == project_id)
            .order_by(ProjectLLMBinding.priority.desc(), ProjectLLMBinding.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_binding(self, binding_id: UUID) -> Optional[ProjectLLMBinding]:
        """获取绑定详情。

        Args:
            binding_id: 绑定 ID

        Returns:
            绑定或 None
        """
        return await self._session.get(ProjectLLMBinding, binding_id)

    async def create_binding(
        self,
        project_id: UUID,
        llm_config_id: UUID,
        is_default: bool = False,
        priority: int = 0,
    ) -> ProjectLLMBinding:
        """创建项目-LLM 绑定。

        Args:
            project_id: 项目 ID
            llm_config_id: LLM 配置 ID
            is_default: 是否设为默认
            priority: 优先级

        Returns:
            创建的绑定
        """
        # 检查配置是否存在
        config = await self.get_config(llm_config_id)
        if not config:
            raise ValueError(f"LLM 配置 {llm_config_id} 不存在")

        # 如果设置为默认，清除其他默认标记
        if is_default:
            stmt = select(ProjectLLMBinding).where(
                ProjectLLMBinding.project_id == project_id,
                ProjectLLMBinding.is_default.is_(True),
            )
            result = await self._session.execute(stmt)
            for binding in result.scalars().all():
                binding.is_default = False

        binding = ProjectLLMBinding(
            project_id=project_id,
            llm_config_id=llm_config_id,
            is_default=is_default,
            priority=priority,
        )
        self._session.add(binding)
        await self._session.commit()
        await self._session.refresh(binding)
        return binding

    async def update_binding(
        self,
        binding_id: UUID,
        is_default: Optional[bool] = None,
        priority: Optional[int] = None,
        enabled: Optional[bool] = None,
    ) -> ProjectLLMBinding:
        """更新绑定。

        Args:
            binding_id: 绑定 ID
            is_default: 是否设为默认（可选）
            priority: 优先级（可选）
            enabled: 是否启用（可选）

        Returns:
            更新后的绑定
        """
        binding = await self.get_binding(binding_id)
        if not binding:
            raise ValueError(f"绑定 {binding_id} 不存在")

        if is_default is not None:
            # 如果设为默认，清除同项目其他默认标记
            if is_default:
                stmt = select(ProjectLLMBinding).where(
                    ProjectLLMBinding.project_id == binding.project_id,
                    ProjectLLMBinding.is_default.is_(True),
                    ProjectLLMBinding.id != binding_id,
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

    async def delete_binding(self, binding_id: UUID) -> None:
        """删除绑定。

        Args:
            binding_id: 绑定 ID
        """
        binding = await self.get_binding(binding_id)
        if not binding:
            raise ValueError(f"绑定 {binding_id} 不存在")
        await self._session.delete(binding)

    async def set_default_binding(self, binding_id: UUID) -> ProjectLLMBinding:
        """设置默认绑定。

        Args:
            binding_id: 绑定 ID

        Returns:
            更新后的绑定
        """
        binding = await self.get_binding(binding_id)
        if not binding:
            raise ValueError(f"绑定 {binding_id} 不存在")

        # 清除同项目其他默认标记
        stmt = select(ProjectLLMBinding).where(
            ProjectLLMBinding.project_id == binding.project_id,
            ProjectLLMBinding.is_default.is_(True),
            ProjectLLMBinding.id != binding_id,
        )
        result = await self._session.execute(stmt)
        for b in result.scalars().all():
            b.is_default = False

        binding.is_default = True
        await self._session.commit()
        await self._session.refresh(binding)
        return binding
