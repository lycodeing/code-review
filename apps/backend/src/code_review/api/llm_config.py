"""LLM 配置 REST API 端点。"""

import logging
import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from code_review.models.db import LLMConfig, ProjectLLMBinding
from code_review.schemas.llm_config import (
    LLMConfigCreate,
    LLMConfigUpdate,
    LLMConfigResponse,
    LLMBindingCreate,
    LLMBindingUpdate,
    LLMBindingResponse,
    TestConnectionRequest,
    TestConnectionResponse,
)
from code_review.services.llm_config_service import LLMConfigService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/llm-configs", tags=["llm-configs"])

# 项目绑定路由
binding_router = APIRouter(prefix="/api/v1/projects/{project_id}/llm-bindings", tags=["llm-bindings"])


async def _mask_config(config: LLMConfig, service: LLMConfigService) -> LLMConfigResponse:
    """将 ORM 模型转换为响应模型（API Key 脱敏）。"""
    decrypted_key = await service.decrypt_api_key(config.api_key)

    # 脱敏：保留前4位和后4位，中间用 ****
    if len(decrypted_key) > 8:
        masked_key = decrypted_key[:4] + "****" + decrypted_key[-4:]
    elif decrypted_key:
        masked_key = "****"
    else:
        masked_key = ""

    return LLMConfigResponse(
        id=config.id,
        name=config.name,
        provider=config.provider,
        model_name=config.model_name,
        api_key=masked_key,
        api_base=config.api_base,
        extra_params=config.extra_params,
        response_format=config.response_format,
        enabled=config.enabled,
        description=config.description,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


# ==================== LLM 配置 CRUD ====================

@router.get("", response_model=list[LLMConfigResponse])
async def list_llm_configs(
    request: Request,
    enabled_only: bool = False,
):
    """列出所有 LLM 配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = LLMConfigService(session, request.app.state.config.server.secret_key)
        configs = await svc.list_configs(enabled_only=enabled_only)
        return [await _mask_config(c, svc) for c in configs]


@router.post("", response_model=LLMConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_llm_config(
    request: Request,
    data: LLMConfigCreate,
):
    """创建新的 LLM 配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = LLMConfigService(session, request.app.state.config.server.secret_key)
        try:
            config = await svc.create_config(
                name=data.name,
                provider=data.provider,
                model_name=data.model_name,
                api_key=data.api_key,
                api_base=data.api_base,
                extra_params=data.extra_params,
                enabled=data.enabled,
                description=data.description,
            )
            await session.commit()
            await session.refresh(config)
            return await _mask_config(config, svc)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{config_id}", response_model=LLMConfigResponse)
async def get_llm_config(
    request: Request,
    config_id: UUID,
):
    """获取指定 LLM 配置详情。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = LLMConfigService(session, request.app.state.config.server.secret_key)
        config = await svc.get_config(config_id)
        if not config:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")
        return await _mask_config(config, svc)


@router.put("/{config_id}", response_model=LLMConfigResponse)
async def update_llm_config(
    request: Request,
    config_id: UUID,
    data: LLMConfigUpdate,
):
    """更新 LLM 配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = LLMConfigService(session, request.app.state.config.server.secret_key)
        try:
            # 过滤 None 值
            update_data = {k: v for k, v in data.model_dump().items() if v is not None}
            config = await svc.update_config(config_id, **update_data)
            await session.commit()
            await session.refresh(config)
            return await _mask_config(config, svc)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_config(
    request: Request,
    config_id: UUID,
):
    """删除 LLM 配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = LLMConfigService(session, request.app.state.config.server.secret_key)
        try:
            await svc.delete_config(config_id)
            await session.commit()
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{config_id}/enable", response_model=LLMConfigResponse)
async def toggle_llm_config(
    request: Request,
    config_id: UUID,
    enabled: bool,
):
    """启用/禁用 LLM 配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = LLMConfigService(session, request.app.state.config.server.secret_key)
        try:
            config = await svc.update_config(config_id, enabled=enabled)
            await session.commit()
            await session.refresh(config)
            return await _mask_config(config, svc)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_connection(
    data: TestConnectionRequest,
):
    """测试 LLM 配置连接。"""
    start_time = time.time()

    try:
        # 处理模型名称：去除提供商前缀（LangChain 不需要）
        # 例如: "openai/claude-opus-4-7" -> "claude-opus-4-7"
        model_name = data.model_name
        if "/" in model_name:
            model_name = model_name.split("/")[-1]

        # 构造模型配置（测试连接时不传 temperature，避免某些模型不支持）
        kwargs = {
            "model": model_name,
            "api_key": data.api_key,
            "max_tokens": 10,
            "timeout": 30,
            "streaming": False,  # 非流式模式，一次性返回
        }

        # 如果有自定义 base_url，使用它
        if data.api_base:
            kwargs["base_url"] = data.api_base

        logger.info(f"测试 LLM 连接: model={model_name}, base_url={data.api_base}")

        # 创建 LLM 实例
        llm = ChatOpenAI(**kwargs)

        # 发送测试消息
        messages = [HumanMessage(content="Hello")]
        response = await llm.ainvoke(messages)

        response_time = (time.time() - start_time) * 1000

        logger.info(f"LLM 连接测试成功: {response_time:.2f}ms")

        return TestConnectionResponse(
            success=True,
            message="连接成功",
            response_time_ms=round(response_time, 2),
            model_info=data.model_name,
        )
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"LLM 连接测试失败: {e}", exc_info=True)
        return TestConnectionResponse(
            success=False,
            message=f"连接失败: {str(e)}",
            response_time_ms=round(response_time, 2),
        )


# ==================== 项目绑定管理 ====================

@binding_router.get("", response_model=list[LLMBindingResponse])
async def list_project_bindings(
    request: Request,
    project_id: UUID,
):
    """获取项目的 LLM 绑定列表。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = LLMConfigService(session, request.app.state.config.server.secret_key)
        bindings = await svc.list_bindings(project_id)

        # 加载关联的 LLM 配置
        result = []
        for binding in bindings:
            config = await svc.get_config(binding.llm_config_id)
            if config:
                result.append(
                    LLMBindingResponse(
                        id=binding.id,
                        project_id=binding.project_id,
                        llm_config_id=binding.llm_config_id,
                        llm_config=await _mask_config(config, svc),
                        is_default=binding.is_default,
                        priority=binding.priority,
                        enabled=binding.enabled,
                        created_at=binding.created_at,
                    )
                )
        return result


@binding_router.post("", response_model=LLMBindingResponse, status_code=status.HTTP_201_CREATED)
async def create_binding(
    request: Request,
    project_id: UUID,
    data: LLMBindingCreate,
):
    """为项目添加 LLM 绑定。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = LLMConfigService(session, request.app.state.config.server.secret_key)
        try:
            binding = await svc.create_binding(
                project_id=project_id,
                llm_config_id=data.llm_config_id,
                is_default=data.is_default,
                priority=data.priority,
            )
            await session.commit()
            await session.refresh(binding)

            # 加载关联的 LLM 配置
            config = await svc.get_config(binding.llm_config_id)
            return LLMBindingResponse(
                id=binding.id,
                project_id=binding.project_id,
                llm_config_id=binding.llm_config_id,
                llm_config=await _mask_config(config, svc) if config else None,
                is_default=binding.is_default,
                priority=binding.priority,
                enabled=binding.enabled,
                created_at=binding.created_at,
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@binding_router.put("/{binding_id}", response_model=LLMBindingResponse)
async def update_binding(
    request: Request,
    project_id: UUID,
    binding_id: UUID,
    data: LLMBindingUpdate,
):
    """更新绑定配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = LLMConfigService(session, request.app.state.config.server.secret_key)
        try:
            # 过滤 None 值
            update_data = {k: v for k, v in data.model_dump().items() if v is not None}
            binding = await svc.update_binding(binding_id, **update_data)
            await session.commit()
            await session.refresh(binding)

            # 加载关联的 LLM 配置
            config = await svc.get_config(binding.llm_config_id)
            return LLMBindingResponse(
                id=binding.id,
                project_id=binding.project_id,
                llm_config_id=binding.llm_config_id,
                llm_config=await _mask_config(config, svc) if config else None,
                is_default=binding.is_default,
                priority=binding.priority,
                enabled=binding.enabled,
                created_at=binding.created_at,
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@binding_router.delete("/{binding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_binding(
    request: Request,
    project_id: UUID,
    binding_id: UUID,
):
    """删除绑定。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = LLMConfigService(session, request.app.state.config.server.secret_key)
        try:
            await svc.delete_binding(binding_id)
            await session.commit()
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@binding_router.patch("/{binding_id}/set-default", response_model=LLMBindingResponse)
async def set_default_binding(
    request: Request,
    project_id: UUID,
    binding_id: UUID,
):
    """设置默认配置。"""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = LLMConfigService(session, request.app.state.config.server.secret_key)
        try:
            binding = await svc.set_default_binding(binding_id)
            await session.commit()
            await session.refresh(binding)

            # 加载关联的 LLM 配置
            config = await svc.get_config(binding.llm_config_id)
            return LLMBindingResponse(
                id=binding.id,
                project_id=binding.project_id,
                llm_config_id=binding.llm_config_id,
                llm_config=await _mask_config(config, svc) if config else None,
                is_default=binding.is_default,
                priority=binding.priority,
                enabled=binding.enabled,
                created_at=binding.created_at,
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
