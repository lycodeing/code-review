"""代码托管平台统一接口定义。

所有平台适配器（GitHub / GitLab / Gitee）必须实现此 Protocol。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator


class PlatformType(str, Enum):
    """支持的平台类型。"""
    GITHUB = "github"
    GITLAB = "gitlab"
    GITEE = "gitee"


class MRState(str, Enum):
    """Merge Request / Pull Request 状态。"""
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


@dataclass(frozen=True)
class FileChange:
    """单个文件的变更信息。"""
    path: str
    old_path: str | None = None
    added: int = 0
    deleted: int = 0
    status: str = "modified"  # added / modified / removed / renamed
    diff: str = ""
    patch: str = ""


@dataclass(frozen=True)
class CommitInfo:
    """提交信息。"""
    sha: str
    message: str
    author: str
    timestamp: str


@dataclass(frozen=True)
class MRInfo:
    """Merge Request / Pull Request 基本信息。"""
    platform: PlatformType
    project_id: str
    mr_id: str
    mr_iid: str  # 平台展示用的短 ID（如 #42）
    title: str
    description: str
    author: str
    source_branch: str
    target_branch: str
    state: MRState
    url: str
    web_url: str = ""


@dataclass(frozen=True)
class CommentPosition:
    """行内评论的定位信息。"""
    path: str
    line: int
    old_line: int | None = None  # 用于删除行的评论
    side: str = "RIGHT"  # LEFT (old) / RIGHT (new)


@dataclass
class PublishComment:
    """待发布的评论。"""
    body: str
    position: CommentPosition | None = None  # None 表示通用评论
    severity: str = "suggestion"  # critical / warning / suggestion / info


@dataclass
class WebhookEvent:
    """Webhook 事件统一模型。"""
    platform: PlatformType
    project_id: str
    mr_id: str
    mr_iid: str
    action: str  # opened / synchronize / updated / closed / merged
    event_id: str  # 用于去重
    mr_title: str | None = None  # MR 标题
    mr_author: str | None = None  # MR 作者
    mr_url: str | None = None  # MR URL
    source_branch: str | None = None  # 源分支
    target_branch: str | None = None  # 目标分支
    raw_payload: dict = field(default_factory=dict)


class PlatformAdapter(ABC):
    """代码托管平台适配器抽象基类。

    每个平台实现类需要封装：
    - API 认证方式
    - 请求格式
    - 错误码处理
    - 速率限制策略
    """

    @property
    @abstractmethod
    def platform_type(self) -> PlatformType:
        """返回平台类型标识。"""

    @abstractmethod
    async def get_mr_info(self, project_id: str, mr_iid: str) -> MRInfo:
        """获取 MR/PR 基本信息。"""

    @abstractmethod
    async def get_mr_changes(self, project_id: str, mr_iid: str) -> list[FileChange]:
        """获取 MR/PR 的变更文件列表及 diff 内容。"""

    @abstractmethod
    async def get_file_content(
        self, project_id: str, file_path: str, ref: str
    ) -> str | None:
        """获取指定分支/引用下文件的完整内容。"""

    @abstractmethod
    async def get_commits(
        self, project_id: str, mr_iid: str
    ) -> list[CommitInfo]:
        """获取 MR/PR 关联的提交历史。"""

    @abstractmethod
    async def publish_comment(
        self,
        project_id: str,
        mr_iid: str,
        comment: PublishComment,
    ) -> str:
        """发布单条评论到 MR/PR，返回评论 ID。"""

    @abstractmethod
    async def publish_comments_batch(
        self,
        project_id: str,
        mr_iid: str,
        comments: list[PublishComment],
    ) -> list[str]:
        """批量发布评论。默认逐条调用 publish_comment，子类可覆盖以利用平台批量 API。"""

    @abstractmethod
    async def verify_webhook_signature(
        self, payload: bytes, signature: str
    ) -> bool:
        """验证 Webhook 请求签名。"""

    @abstractmethod
    async def parse_webhook_event(self, payload: dict) -> WebhookEvent | None:
        """解析 Webhook 负载为统一事件模型。不相关事件返回 None。"""

    @abstractmethod
    async def health_check(self) -> bool:
        """检查平台连接和认证是否正常。"""
