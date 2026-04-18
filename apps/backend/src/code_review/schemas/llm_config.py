"""LLM 配置 Pydantic 模型。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# 支持的响应格式列表
SUPPORTED_RESPONSE_FORMATS = [
    "auto",  # 自动检测（默认）
    "json",  # 标准 JSON 格式（OpenAI/Zhipu/DeepSeek 等）
    "anthropic_thinking",  # Anthropic Thinking 模式
    "xml",  # XML 格式
    "plain_text",  # 纯文本格式
]


class LLMConfigCreate(BaseModel):
    """创建 LLM 配置请求。"""

    name: str = Field(..., min_length=1, max_length=255, description="配置名称（唯一）")
    provider: str = Field(..., pattern="^(openai|anthropic|deepseek|ollama|azure|bedrock|dashscope|zhipu)$")
    model_name: str = Field(..., min_length=1, max_length=128, description="模型名称")
    api_key: str = Field(..., min_length=0, description="API 密钥")
    api_base: str = Field(default="", description="API 基础地址")
    extra_params: dict | None = Field(default=None, description="额外参数")
    response_format: str = Field(
        default="auto",
        description="响应格式：auto/json/anthropic_thinking/xml/plain_text",
    )
    enabled: bool = Field(default=True, description="是否启用")
    description: str = Field(default="", max_length=512, description="说明")

    @field_validator("response_format")
    @classmethod
    def validate_response_format(cls, v: str) -> str:
        """验证响应格式是否有效。"""
        if v not in SUPPORTED_RESPONSE_FORMATS:
            raise ValueError(
                f"不支持的响应格式: {v}。支持的格式: {', '.join(SUPPORTED_RESPONSE_FORMATS)}"
            )
        return v


class LLMConfigUpdate(BaseModel):
    """更新 LLM 配置请求（所有字段可选）。"""

    provider: str | None = Field(None, pattern="^(openai|anthropic|deepseek|ollama|azure|bedrock|dashscope|zhipu)$")
    model_name: str | None = Field(None, min_length=1, max_length=128)
    api_key: str | None = None
    api_base: str | None = None
    extra_params: dict | None = None
    response_format: str | None = Field(
        default=None,
        description="响应格式：auto/json/anthropic_thinking/xml/plain_text",
    )
    enabled: bool | None = None
    description: str | None = Field(None, max_length=512)

    @field_validator("response_format")
    @classmethod
    def validate_response_format(cls, v: str | None) -> str | None:
        """验证响应格式是否有效。"""
        if v is not None and v not in SUPPORTED_RESPONSE_FORMATS:
            raise ValueError(
                f"不支持的响应格式: {v}。支持的格式: {', '.join(SUPPORTED_RESPONSE_FORMATS)}"
            )
        return v


class LLMConfigResponse(BaseModel):
    """LLM 配置响应。"""

    id: UUID
    name: str
    provider: str
    model_name: str
    api_key: str  # 脱敏后返回，格式：前4位****后4位
    api_base: str
    extra_params: dict | None
    response_format: str = Field(description="响应格式")
    enabled: bool
    description: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LLMBindingCreate(BaseModel):
    """创建项目-LLM 绑定请求。"""

    llm_config_id: UUID
    is_default: bool = Field(default=False, description="是否设为默认")
    priority: int = Field(default=0, ge=0, le=100, description="优先级（0-100）")


class LLMBindingUpdate(BaseModel):
    """更新绑定请求。"""

    is_default: bool | None = None
    priority: int | None = Field(None, ge=0, le=100)
    enabled: bool | None = None


class LLMBindingResponse(BaseModel):
    """绑定响应。"""

    id: UUID
    project_id: UUID
    llm_config_id: UUID
    llm_config: LLMConfigResponse | None = None
    is_default: bool
    priority: int
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TestConnectionRequest(BaseModel):
    """测试连接请求。"""

    provider: str
    model_name: str
    api_key: str
    api_base: str = ""
    extra_params: dict | None = None
    response_format: str = Field(default="auto", description="响应格式")


class TestConnectionResponse(BaseModel):
    """测试连接响应。"""

    success: bool
    message: str
    response_time_ms: float | None = None
    model_info: str | None = None
