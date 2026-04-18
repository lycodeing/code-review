"""平台适配器工厂。"""

import logging

from code_review.adapters.github_adapter import GitHubAdapter
from code_review.adapters.gitlab_adapter import GitLabAdapter
from code_review.adapters.gitee_adapter import GiteeAdapter
from code_review.core.platform import PlatformType, PlatformAdapter
from code_review.models.db import PlatformConfig

logger = logging.getLogger(__name__)


def create_adapter(
    platform: PlatformType | str,
    platform_config: PlatformConfig,
    project_webhook_secret: str = "",
) -> PlatformAdapter:
    """根据平台类型和配置创建对应的适配器实例。

    Args:
        platform: 平台类型。
        platform_config: 数据库中的平台配置。
        project_webhook_secret: 项目级别的 Webhook 密钥（覆盖全局配置）。

    Returns:
        平台适配器实例。

    Raises:
        ValueError: 不支持的平台类型。
    """
    if isinstance(platform, str):
        platform = PlatformType(platform)

    match platform:
        case PlatformType.GITHUB:
            adapter = GitHubAdapter(
                token=platform_config.access_token,
                api_url=platform_config.api_url or "https://api.github.com",
            )
            secret = project_webhook_secret or platform_config.webhook_secret
            adapter.set_webhook_secret(secret)

        case PlatformType.GITLAB:
            adapter = GitLabAdapter(
                token=platform_config.access_token,
                api_url=platform_config.api_url or "https://gitlab.com/api/v4",
            )
            secret = project_webhook_secret or platform_config.webhook_secret
            adapter.set_webhook_secret(secret)

        case PlatformType.GITEE:
            adapter = GiteeAdapter(
                token=platform_config.access_token,
                api_url=platform_config.api_url or "https://gitee.com/api/v5",
            )
            secret = project_webhook_secret or platform_config.webhook_secret
            adapter.set_webhook_secret(secret)

        case _:
            raise ValueError(f"Unsupported platform: {platform}")

    return adapter
