"""平台适配器工厂。"""

from code_review.adapters.github_adapter import GitHubAdapter
from code_review.adapters.gitlab_adapter import GitLabAdapter
from code_review.adapters.gitee_adapter import GiteeAdapter
from code_review.core.platform import PlatformType, PlatformAdapter
from code_review.models.config import AppConfig


def create_adapter(
    platform: PlatformType | str,
    config: AppConfig,
    project_webhook_secret: str = "",
) -> PlatformAdapter:
    """根据平台类型创建对应的适配器实例。

    Args:
        platform: 平台类型。
        config: 应用配置。
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
                token=config.github.token,
                api_url=config.github.api_url,
            )
            secret = project_webhook_secret or config.github.webhook_secret
            adapter.set_webhook_secret(secret)

        case PlatformType.GITLAB:
            adapter = GitLabAdapter(
                token=config.gitlab.token,
                api_url=config.gitlab.api_url,
            )
            secret = project_webhook_secret or config.gitlab.webhook_secret
            adapter.set_webhook_secret(secret)

        case PlatformType.GITEE:
            adapter = GiteeAdapter(
                token=config.gitee.token,
                api_url=config.gitee.api_url,
            )
            secret = project_webhook_secret or config.gitee.webhook_secret
            adapter.set_webhook_secret(secret)

        case _:
            raise ValueError(f"Unsupported platform: {platform}")

    return adapter
