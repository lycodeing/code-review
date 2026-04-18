"""数据库 ORM 模型（SQLAlchemy async）。"""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""
    pass


class Project(Base):
    """项目配置表 —— 支持多项目。"""
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True, comment="项目名称")
    platform = Column(String(50), nullable=False, comment="平台类型: github/gitlab/gitee")
    platform_project_id = Column(String(255), nullable=False, comment="平台上的项目 ID")
    webhook_secret = Column(String(512), nullable=True, comment="Webhook 签名密钥")
    config = Column(JSON, nullable=True, comment="项目级配置覆盖（文件过滤、评论模式等）")
    enabled = Column(Integer, nullable=False, default=1, comment="是否启用")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    reviews = relationship("ReviewTask", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Project {self.name} ({self.platform})>"


class ReviewTask(Base):
    """评审任务表。"""
    __tablename__ = "review_tasks"

    class Status(str):
        PENDING = "pending"
        IN_PROGRESS = "in_progress"
        COMPLETED = "completed"
        FAILED = "failed"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    mr_iid = Column(String(64), nullable=False, comment="平台展示用的 MR 短 ID")
    mr_title = Column(String(512), nullable=True)
    mr_author = Column(String(255), nullable=True)
    mr_url = Column(Text, nullable=True)
    source_branch = Column(String(255), nullable=True)
    target_branch = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default=Status.PENDING, index=True)
    event_id = Column(String(255), nullable=True, comment="用于幂等去重的事件 ID")
    trigger_action = Column(String(64), nullable=True, comment="触发动作: opened/synchronize/updated")
    model_name = Column(String(128), nullable=True, comment="使用的 LLM 模型")
    total_comments = Column(Integer, nullable=True, default=0)
    critical_count = Column(Integer, nullable=True, default=0)
    warning_count = Column(Integer, nullable=True, default=0)
    summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    celery_task_id = Column(String(255), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    project = relationship("Project", back_populates="reviews")
    comments = relationship("ReviewComment", back_populates="task", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("project_id", "mr_iid", "event_id", name="uq_review_event"),
        Index("ix_review_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<ReviewTask {self.id} [{self.status}]>"


class PromptTemplate(Base):
    """Prompt 模板表 —— 数据库管理模板。"""
    __tablename__ = "prompt_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True, comment="模板名称（唯一标识）")
    content = Column(Text, nullable=False, comment="模板内容（支持 {{diff}} / {{files_context}} 占位符）")
    category = Column(String(64), nullable=False, default="default", comment="模板分类：python/java/go/default 等")
    locale = Column(String(10), nullable=False, default="zh", comment="语言标识：zh / en")
    enabled = Column(Integer, nullable=False, default=1, comment="是否启用：1 启用 / 0 禁用")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    project_bindings = relationship(
        "ProjectPromptBinding",
        back_populates="template",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("name", name="uq_prompt_template_name"),
        Index("ix_prompt_template_category", "category"),
        Index("ix_prompt_template_locale", "locale"),
    )

    def __repr__(self) -> str:
        return f"<PromptTemplate {self.name} [{self.category}/{self.locale}]>"


class ReviewComment(Base):
    """评审意见表。"""
    __tablename__ = "review_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("review_tasks.id"), nullable=False)
    file_path = Column(String(1024), nullable=False)
    line_start = Column(Integer, nullable=False)
    line_end = Column(Integer, nullable=True)
    severity = Column(String(32), nullable=False, comment="critical/warning/suggestion/info")
    message = Column(Text, nullable=False)
    suggestion = Column(Text, nullable=True)
    platform_comment_id = Column(String(255), nullable=True, comment="平台上已发布的评论 ID")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    task = relationship("ReviewTask", back_populates="comments")

    def __repr__(self) -> str:
        return f"<ReviewComment {self.file_path}:{self.line_start} [{self.severity}]>"


class PlatformConfig(Base):
    """代码平台配置表。"""
    __tablename__ = "platform_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform = Column(String(32), nullable=False, unique=True, comment="平台标识: github/gitlab/gitee")
    access_token = Column(Text, nullable=False, default="", comment="API 访问令牌（加密）")
    webhook_secret = Column(Text, nullable=False, default="", comment="Webhook 签名密钥（加密）")
    api_url = Column(String(512), nullable=False, default="", comment="API 基础地址")
    enabled = Column(Boolean, nullable=False, default=True, comment="是否启用")
    description = Column(String(512), nullable=False, default="", comment="说明文字")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    notification_bindings = relationship(
        "PlatformNotificationBinding",
        back_populates="platform",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<PlatformConfig {self.platform}>"


class NotificationConfig(Base):
    """通知渠道配置表。"""
    __tablename__ = "notification_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel = Column(String(32), nullable=False, unique=True, comment="渠道标识: dingtalk/feishu")
    enabled = Column(Boolean, nullable=False, default=False, comment="是否启用")
    webhook_url = Column(String(1024), nullable=False, default="", comment="Webhook 地址")
    secret = Column(Text, nullable=False, default="", comment="签名密钥（加密）")
    at_mobiles = Column(String(1024), nullable=False, default="", comment="@人手机号（逗号分隔）")
    description = Column(String(512), nullable=False, default="", comment="说明文字")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    platform_bindings = relationship(
        "PlatformNotificationBinding",
        back_populates="notification",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<NotificationConfig {self.channel}>"


class PlatformNotificationBinding(Base):
    """平台-通知渠道关联表（多对多）。"""
    __tablename__ = "platform_notification_bindings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform_id = Column(
        UUID(as_uuid=True),
        ForeignKey("platform_configs.id", ondelete="CASCADE"),
        nullable=False,
    )
    notification_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notification_configs.id", ondelete="CASCADE"),
        nullable=False,
    )
    enabled = Column(Boolean, nullable=False, default=True, comment="绑定是否启用")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    platform = relationship("PlatformConfig", back_populates="notification_bindings")
    notification = relationship("NotificationConfig", back_populates="platform_bindings")

    __table_args__ = (
        UniqueConstraint("platform_id", "notification_id", name="uq_platform_notification"),
        Index("idx_bindings_platform", "platform_id"),
        Index("idx_bindings_notification", "notification_id"),
    )

    def __repr__(self) -> str:
        return f"<PlatformNotificationBinding {self.platform_id}->{self.notification_id}>"


class LLMConfig(Base):
    """LLM 提供商配置表。"""
    __tablename__ = "llm_configs"

    class ResponseFormat(str):
        """支持的 LLM 响应格式。"""
        AUTO = "auto"  # 自动检测（默认）
        JSON = "json"  # 标准 JSON 格式（OpenAI/Zhipu/DeepSeek 等）
        ANTHROPIC_THINKING = "anthropic_thinking"  # Anthropic Thinking 模式
        XML = "xml"  # XML 格式
        PLAIN_TEXT = "plain_text"  # 纯文本格式

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True, comment="配置名称（唯一标识）")
    provider = Column(String(64), nullable=False, comment="提供商：openai/anthropic/deepseek/ollama/azure/bedrock/dashscope/zhipu")
    model_name = Column(String(128), nullable=False, comment="模型名称")
    api_key = Column(Text, nullable=False, default="", comment="API 密钥（加密存储）")
    api_base = Column(String(512), nullable=False, default="", comment="API 基础地址")
    extra_params = Column(JSON, nullable=True, comment="额外参数（temperature/max_tokens/等）")
    response_format = Column(
        String(32),
        nullable=False,
        default=ResponseFormat.AUTO,
        comment="响应格式：auto/json/anthropic_thinking/xml/plain_text",
    )
    enabled = Column(Boolean, nullable=False, default=True, comment="是否启用")
    description = Column(String(512), nullable=False, default="", comment="说明文字")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    project_bindings = relationship(
        "ProjectLLMBinding",
        back_populates="llm_config",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_llm_configs_provider", "provider"),
        Index("idx_llm_configs_enabled", "enabled"),
        Index("idx_llm_configs_response_format", "response_format"),
    )

    def __repr__(self) -> str:
        return f"<LLMConfig {self.name} [{self.provider}/{self.model_name}]>"


class ProjectLLMBinding(Base):
    """项目-LLM 配置关联表（多对多）。"""
    __tablename__ = "project_llm_bindings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    llm_config_id = Column(
        UUID(as_uuid=True),
        ForeignKey("llm_configs.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_default = Column(Boolean, nullable=False, default=False, comment="是否为项目默认配置")
    priority = Column(Integer, nullable=False, default=0, comment="优先级（数字越大优先级越高）")
    enabled = Column(Boolean, nullable=False, default=True, comment="绑定是否启用")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    project = relationship("Project")
    llm_config = relationship("LLMConfig", back_populates="project_bindings")

    __table_args__ = (
        UniqueConstraint("project_id", "llm_config_id", name="uq_project_llm"),
        Index("idx_project_llm_project", "project_id"),
        Index("idx_project_llm_config", "llm_config_id"),
    )

    def __repr__(self) -> str:
        return f"<ProjectLLMBinding {self.project_id}->{self.llm_config_id}>"


class ProjectPromptBinding(Base):
    """项目-Prompt 模板关联表（多对多）。"""
    __tablename__ = "project_prompt_bindings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("prompt_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_default = Column(Boolean, nullable=False, default=False, comment="是否为项目默认模板")
    priority = Column(Integer, nullable=False, default=0, comment="优先级（数字越大优先级越高）")
    enabled = Column(Boolean, nullable=False, default=True, comment="绑定是否启用")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    project = relationship("Project")
    template = relationship("PromptTemplate", back_populates="project_bindings")

    __table_args__ = (
        UniqueConstraint("project_id", "template_id", name="uq_project_prompt"),
        Index("idx_project_prompt_project", "project_id"),
        Index("idx_project_prompt_template", "template_id"),
    )

    def __repr__(self) -> str:
        return f"<ProjectPromptBinding {self.project_id}->{self.template_id}>"
