"""平台适配层。"""

from code_review.adapters.github_adapter import GitHubAdapter
from code_review.adapters.gitlab_adapter import GitLabAdapter
from code_review.adapters.gitee_adapter import GiteeAdapter
from code_review.adapters.factory import create_adapter

__all__ = ["GitHubAdapter", "GitLabAdapter", "GiteeAdapter", "create_adapter"]
