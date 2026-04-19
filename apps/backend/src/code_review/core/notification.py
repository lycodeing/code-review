"""通知渠道统一接口定义。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class NotificationPayload:
    """通知内容载荷。"""
    mr_title: str
    mr_author: str
    mr_url: str
    project_name: str
    summary: str
    critical_count: int = 0
    warning_count: int = 0
    suggestion_count: int = 0
    info_count: int = 0
    detail_link: str = ""
    # 模板渲染后填充，非空时渠道优先使用此内容
    rendered_title: str | None = field(default=None)
    rendered_body: str | None = field(default=None)


class NotificationChannel(ABC):
    """通知渠道抽象基类。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """渠道名称标识。"""

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """是否启用。"""

    @abstractmethod
    async def send(self, payload: NotificationPayload) -> bool:
        """发送通知，返回是否成功。"""

    @abstractmethod
    async def health_check(self) -> bool:
        """检查通知渠道是否可用。"""
