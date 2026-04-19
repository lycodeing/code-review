"""大模型评审接口定义。

使用 LiteLLM 作为统一调用层，所有 LLM 实现必须遵循此 Protocol。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from code_review.core.platform import FileChange


class Severity(str, Enum):
    """评审意见严重程度。"""
    CRITICAL = "critical"
    WARNING = "warning"
    SUGGESTION = "suggestion"
    INFO = "info"


@dataclass(frozen=True)
class ReviewComment:
    """大模型返回的单条评审意见。"""
    file_path: str
    line_start: int
    line_end: int
    severity: Severity
    message: str
    suggestion: str = ""  # 具体修复建议


@dataclass
class ReviewResult:
    """一次完整评审的结果。"""
    comments: list[ReviewComment] = field(default_factory=list)
    summary: str = ""  # 整体评审摘要
    model: str = ""  # 使用的模型名称
    total_tokens: int = 0
    elapsed_seconds: float = 0.0


class LLMReviewer(ABC):
    """大模型评审器抽象基类。"""

    @abstractmethod
    async def review(
        self,
        diff: str,
        files: list[FileChange],
        prompt_template: str,
        task_id=None,
        session_factory=None,
    ) -> ReviewResult:
        """执行代码评审。

        Args:
            diff: 完整的 diff 内容。
            files: 变更文件列表。
            prompt_template: 渲染后的 prompt 模板文本。
            task_id: 评审任务 UUID，有值时将调用记录写入 api_call_logs。
            session_factory: 数据库 session 工厂，用于写日志。

        Returns:
            结构化的评审结果。
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """检查 LLM 服务是否可用。"""
