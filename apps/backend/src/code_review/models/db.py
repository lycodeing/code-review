"""数据库 ORM 模型（SQLAlchemy async）。"""

import uuid
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
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
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc), onupdate=lambda: datetime.now(tz=timezone.utc))

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
        SKIPPED = "skipped"

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
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))

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
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc), onupdate=lambda: datetime.now(tz=timezone.utc))

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
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))

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
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc), onupdate=lambda: datetime.now(tz=timezone.utc))

    notification_bindings = relationship(
        "PlatformNotificationBinding",
        back_populates="platform",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<PlatformConfig {self.platform}>"


class NotificationTemplate(Base):
    """通知消息模板表。"""
    __tablename__ = "notification_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(128), nullable=False, unique=True, comment="模板名称（唯一标识）")
    channel = Column(String(32), nullable=False, comment="渠道标识: dingtalk / feishu")
    description = Column(String(512), nullable=False, default="", comment="模板描述")
    title_template = Column(String(512), nullable=False, default="", comment="卡片标题模板，支持 {{变量}} 语法")
    body_template = Column(Text, nullable=False, default="", comment="正文 Markdown 模板，支持 {{变量}} 语法")
    enabled = Column(Boolean, nullable=False, default=True, comment="是否启用")
    is_default = Column(Boolean, nullable=False, default=False, comment="是否为该渠道的内置默认模板（不可删除）")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc), onupdate=lambda: datetime.now(tz=timezone.utc))

    # 渠道配置中引用此模板
    notification_configs = relationship(
        "NotificationConfig",
        back_populates="template",
        foreign_keys="NotificationConfig.template_id",
    )
    # 项目级绑定
    project_bindings = relationship(
        "ProjectNotificationTemplateBinding",
        back_populates="template",
        foreign_keys="ProjectNotificationTemplateBinding.template_id",
    )

    __table_args__ = (
        Index("idx_notification_templates_channel", "channel"),
        Index("idx_notification_templates_is_default", "is_default"),
    )

    def __repr__(self) -> str:
        return f"<NotificationTemplate {self.name} [{self.channel}]>"


class NotificationConfig(Base):
    """通知渠道配置表。"""
    __tablename__ = "notification_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel = Column(String(32), nullable=False, unique=True, comment="渠道标识: dingtalk/feishu/email")
    enabled = Column(Boolean, nullable=False, default=False, comment="是否启用")
    webhook_url = Column(String(1024), nullable=False, default="", comment="Webhook 地址")
    secret = Column(Text, nullable=False, default="", comment="签名密钥（加密）")
    at_mobiles = Column(String(1024), nullable=False, default="", comment="@人手机号（逗号分隔）")
    description = Column(String(512), nullable=False, default="", comment="说明文字")
    extra_config = Column(JSON, nullable=True, comment="渠道特有配置（如 email 的 SMTP 设置）")
    # 渠道默认模板（NULL 时使用内置 is_default 模板）
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notification_templates.id", ondelete="SET NULL"),
        nullable=True,
        comment="渠道默认模板，空时使用内置默认模板",
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc), onupdate=lambda: datetime.now(tz=timezone.utc))

    platform_bindings = relationship(
        "PlatformNotificationBinding",
        back_populates="notification",
        cascade="all, delete-orphan",
    )
    # 渠道默认模板关联
    template = relationship(
        "NotificationTemplate",
        back_populates="notification_configs",
        foreign_keys=[template_id],
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
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))

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
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc), onupdate=lambda: datetime.now(tz=timezone.utc))

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
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))

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
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))

    project = relationship("Project")
    template = relationship("PromptTemplate", back_populates="project_bindings")

    __table_args__ = (
        UniqueConstraint("project_id", "template_id", name="uq_project_prompt"),
        Index("idx_project_prompt_project", "project_id"),
        Index("idx_project_prompt_template", "template_id"),
    )

    def __repr__(self) -> str:
        return f"<ProjectPromptBinding {self.project_id}->{self.template_id}>"


class ProjectNotificationTemplateBinding(Base):
    """项目级通知模板绑定表（每个项目每个渠道只有一条）。"""
    __tablename__ = "project_notification_template_bindings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="项目 ID",
    )
    notification_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notification_configs.id", ondelete="CASCADE"),
        nullable=False,
        comment="通知渠道配置 ID",
    )
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notification_templates.id", ondelete="SET NULL"),
        nullable=True,
        comment="指定模板，NULL 时降级到渠道默认模板",
    )
    enabled = Column(Boolean, nullable=False, default=True, comment="此绑定是否启用")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))

    project = relationship("Project")
    notification = relationship("NotificationConfig")
    template = relationship(
        "NotificationTemplate",
        back_populates="project_bindings",
        foreign_keys=[template_id],
    )

    __table_args__ = (
        UniqueConstraint("project_id", "notification_id", name="uq_project_notification_binding"),
        Index("idx_proj_notif_tpl_project", "project_id"),
        Index("idx_proj_notif_tpl_notification", "notification_id"),
        Index("idx_proj_notif_tpl_template", "template_id"),
    )

    def __repr__(self) -> str:
        return f"<ProjectNotificationTemplateBinding {self.project_id}->{self.notification_id}>"


class ApiCallLog(Base):
    """外部 API 调用日志表 —— 统一记录 LLM 调用和通知发送的请求/响应详情。"""
    __tablename__ = "api_call_logs"

    class CallType(StrEnum):
        LLM = "llm"
        NOTIFICATION = "notification"

    class CallStatus(StrEnum):
        SUCCESS = "success"
        FAILED = "failed"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("review_tasks.id", ondelete="CASCADE"),
        nullable=True,
        comment="关联的评审任务 ID",
    )
    call_type = Column(String(32), nullable=False, comment="调用类型: llm / notification")
    provider = Column(String(64), nullable=True, comment="提供商: dingtalk/feishu/gpt-4/claude-... 等")
    method = Column(String(16), nullable=True, comment="HTTP 方法")
    url = Column(Text, nullable=True, comment="端点 URL（已脱敏）")
    request_headers = Column(JSONB, nullable=True, comment="请求头（敏感字段已脱敏）")
    request_body = Column(JSONB, nullable=True, comment="请求体")
    response_status = Column(Integer, nullable=True, comment="HTTP 响应状态码")
    response_body = Column(JSONB, nullable=True, comment="响应内容（超大内容已截断）")
    status = Column(String(32), nullable=False, default=CallStatus.SUCCESS, comment="调用结果: success / failed")
    error_message = Column(Text, nullable=True, comment="失败时的错误详情")
    duration_ms = Column(Integer, nullable=True, comment="请求耗时（毫秒）")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))

    task = relationship("ReviewTask", backref="api_call_logs")

    __table_args__ = (
        Index("idx_api_call_logs_task_id", "task_id"),
        Index("idx_api_call_logs_call_type", "call_type"),
        Index("idx_api_call_logs_status", "status"),
        Index("idx_api_call_logs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ApiCallLog {self.call_type}/{self.provider} [{self.status}]>"


class ReviewRule(Base):
    """评审规则定义表。"""
    __tablename__ = "review_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True, comment="规则名称（唯一标识）")
    description = Column(Text, nullable=False, default="", comment="规则描述")
    rule_type = Column(String(32), nullable=False, default="regex", comment="规则类型: regex")
    pattern = Column(Text, nullable=False, comment="匹配模式（正则表达式）")
    severity = Column(String(32), nullable=False, default="warning", comment="命中时的严重程度")
    message = Column(Text, nullable=False, comment="命中时的提示信息")
    file_pattern = Column(String(512), nullable=False, default="**", comment="适用的文件 glob 模式")
    enabled = Column(Boolean, nullable=False, default=True, comment="是否启用")
    is_builtin = Column(Boolean, nullable=False, default=False, comment="是否为内置模板规则")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc), onupdate=lambda: datetime.now(tz=timezone.utc))

    project_bindings = relationship(
        "ProjectRuleBinding",
        back_populates="rule",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_review_rules_enabled", "enabled"),
    )

    def __repr__(self) -> str:
        return f"<ReviewRule {self.name} [{self.rule_type}]>"


class ProjectRuleBinding(Base):
    """项目-评审规则绑定表（多对多）。"""
    __tablename__ = "project_rule_bindings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("review_rules.id", ondelete="CASCADE"),
        nullable=False,
    )
    enabled = Column(Boolean, nullable=False, default=True, comment="绑定是否启用")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))

    project = relationship("Project")
    rule = relationship("ReviewRule", back_populates="project_bindings")

    __table_args__ = (
        UniqueConstraint("project_id", "rule_id", name="uq_project_rule"),
        Index("idx_project_rule_project", "project_id"),
        Index("idx_project_rule_rule", "rule_id"),
    )

    def __repr__(self) -> str:
        return f"<ProjectRuleBinding {self.project_id}->{self.rule_id}>"


class CommentReply(Base):
    """评论回复表 — 支持多轮评审对话。"""
    __tablename__ = "comment_replies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("review_comments.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_reply_id = Column(
        UUID(as_uuid=True),
        ForeignKey("comment_replies.id", ondelete="CASCADE"),
        nullable=True,
        comment="父回复 ID（支持嵌套回复）",
    )
    author = Column(String(255), nullable=False, default="user", comment="回复作者")
    content = Column(Text, nullable=False, comment="回复内容")
    source = Column(String(32), nullable=False, default="user", comment="来源: user / llm / system")
    llm_context = Column(JSON, nullable=True, comment="LLM 对话上下文")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))

    comment = relationship("ReviewComment", backref="replies")
    parent = relationship("CommentReply", remote_side="CommentReply.id", backref="children")

    __table_args__ = (
        Index("idx_comment_replies_comment", "comment_id"),
        Index("idx_comment_replies_parent", "parent_reply_id"),
    )

    def __repr__(self) -> str:
        return f"<CommentReply {self.id} [{self.source}]>"
