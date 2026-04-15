"""应用配置模型（Pydantic Settings）。"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PlatformConfig(BaseSettings):
    """单个平台连接配置。"""
    token: str = ""
    url: str = ""  # 自托管平台的基础 URL（GitLab/Gitee）
    webhook_secret: str = ""


class GitHubConfig(PlatformConfig):
    """GitHub 配置。"""
    api_url: str = "https://api.github.com"


class GitLabConfig(PlatformConfig):
    """GitLab 配置。"""
    api_url: str = "https://gitlab.com/api/v4"


class GiteeConfig(PlatformConfig):
    """Gitee 配置。"""
    api_url: str = "https://gitee.com/api/v5"


class LLMConfig(BaseSettings):
    """大模型配置。"""
    model: str = "gpt-4"
    api_key: str = ""
    api_base: str = ""
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 120


class FeishuConfig(BaseSettings):
    """飞书通知配置。"""
    enabled: bool = False
    webhook_url: str = ""
    secret: str = ""  # 签名密钥（可选）


class DingTalkConfig(BaseSettings):
    """钉钉通知配置。"""
    enabled: bool = False
    webhook_url: str = ""
    secret: str = ""  # 签名密钥（可选）


class EmailConfig(BaseSettings):
    """邮件通知配置（预留）。"""
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    from_addr: str = ""
    to_addrs: list[str] = []


class ReviewConfig(BaseSettings):
    """评审行为配置。"""
    comment_language: str = "zh"  # zh / en
    comment_mode: str = "detailed"  # detailed / summary
    max_comments_per_mr: int = 50
    max_diff_lines: int = 5000  # 超过此行数截断
    severity_threshold_for_summary: int = 30  # 评论数超过此值时切换为摘要模式
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "*.lock", "*.min.js", "*.min.css", "vendor/**",
            "node_modules/**", "*.generated.*", "dist/**",
        ]
    )


class DatabaseConfig(BaseSettings):
    """数据库配置。"""
    url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/code_review"
    echo: bool = False
    pool_size: int = 10


class RedisConfig(BaseSettings):
    """Redis 配置。"""
    url: str = "redis://localhost:6379/0"


class CeleryConfig(BaseSettings):
    """Celery 配置。"""
    broker_url: str = "redis://localhost:6379/1"
    result_backend: str = "redis://localhost:6379/2"
    task_serializer: str = "json"
    result_serializer: str = "json"
    timezone: str = "Asia/Shanghai"


class ServerConfig(BaseSettings):
    """Web 服务配置。"""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    secret_key: str = "change-me-in-production"
    log_level: str = "INFO"


class AppConfig(BaseSettings):
    """应用全局配置。"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        env_prefix="CODE_REVIEW_",
    )

    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    celery: CeleryConfig = Field(default_factory=CeleryConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)
    gitlab: GitLabConfig = Field(default_factory=GitLabConfig)
    gitee: GiteeConfig = Field(default_factory=GiteeConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    dingtalk: DingTalkConfig = Field(default_factory=DingTalkConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
