"""系统配置 Pydantic 模型。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SelectOption(BaseModel):
    """select 类型的选项。"""

    label: str
    value: str


class SystemSettingResponse(BaseModel):
    """系统配置响应。"""

    key: str
    value: str
    value_type: str
    input_type: str
    category: str
    label: str
    description: str
    unit: str
    default_value: str
    options: list[SelectOption] | None = None
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SystemSettingBatchItem(BaseModel):
    """批量更新中的单条配置。"""

    key: str = Field(..., min_length=1, max_length=128)
    value: str = Field(..., min_length=1)


class SystemSettingBatchUpdate(BaseModel):
    """批量更新系统配置请求。"""

    settings: list[SystemSettingBatchItem] = Field(..., min_length=1)


class CategoryResponse(BaseModel):
    """配置分类信息。"""

    key: str
    label: str
    count: int


# 分类 key → 中文标签 映射
CATEGORY_LABELS: dict[str, str] = {
    "timeout": "超时配置",
    "general": "通用配置",
}
