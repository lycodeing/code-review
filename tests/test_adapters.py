"""平台适配器测试（使用 mock）。"""

import pytest

from code_review.adapters.factory import create_adapter
from code_review.adapters.github_adapter import GitHubAdapter
from code_review.adapters.gitlab_adapter import GitLabAdapter
from code_review.adapters.gitee_adapter import GiteeAdapter
from code_review.core.platform import PlatformType
from code_review.models.config import AppConfig


@pytest.fixture
def config() -> AppConfig:
    return AppConfig(
        github={"token": "test-token", "api_url": "https://api.github.com"},
        gitlab={"token": "test-token", "api_url": "https://gitlab.com/api/v4"},
        gitee={"token": "test-token", "api_url": "https://gitee.com/api/v5"},
    )


class TestAdapterFactory:
    """适配器工厂测试。"""

    def test_create_github(self, config):
        adapter = create_adapter(PlatformType.GITHUB, config)
        assert isinstance(adapter, GitHubAdapter)
        assert adapter.platform_type == PlatformType.GITHUB

    def test_create_gitlab(self, config):
        adapter = create_adapter(PlatformType.GITLAB, config)
        assert isinstance(adapter, GitLabAdapter)
        assert adapter.platform_type == PlatformType.GITLAB

    def test_create_gitee(self, config):
        adapter = create_adapter(PlatformType.GITEE, config)
        assert isinstance(adapter, GiteeAdapter)
        assert adapter.platform_type == PlatformType.GITEE

    def test_create_by_string(self, config):
        adapter = create_adapter("github", config)
        assert isinstance(adapter, GitHubAdapter)

    def test_unsupported_platform(self, config):
        with pytest.raises(ValueError, match="Unsupported platform"):
            create_adapter("bitbucket", config)


class TestGitHubAdapter:
    def test_parse_project_id(self):
        owner, repo = GitHubAdapter._parse_project_id("octocat/hello-world")
        assert owner == "octocat"
        assert repo == "hello-world"

    def test_parse_project_id_invalid(self):
        with pytest.raises(ValueError):
            GitHubAdapter._parse_project_id("invalid")

    def test_format_comment_body_critical(self):
        from code_review.core.platform import PublishComment
        comment = PublishComment(body="Fix this", severity="critical")
        body = GitHubAdapter._format_comment_body(comment)
        assert "[CRITICAL]" in body
        assert "Fix this" in body


class TestGitLabAdapter:
    def test_url_encode(self):
        from code_review.adapters.gitlab_adapter import _url_encode
        assert _url_encode("my-group/my-project") == "my-group%2Fmy-project"
        assert _url_encode("12345") == "12345"


class TestGiteeAdapter:
    def test_parse_project_id(self):
        owner, repo = GiteeAdapter._parse_project_id("myorg/myrepo")
        assert owner == "myorg"
        assert repo == "myrepo"

    def test_parse_project_id_invalid(self):
        with pytest.raises(ValueError):
            GiteeAdapter._parse_project_id("invalid")


class TestWebhookParsing:
    """Webhook 事件解析测试。"""

    @pytest.mark.asyncio
    async def test_github_parse_pr_opened(self):
        adapter = GitHubAdapter(token="test")
        payload = {
            "action": "opened",
            "pull_request": {
                "id": 123,
                "number": 42,
                "title": "Test PR",
                "user": {"login": "testuser"},
                "head": {"ref": "feature"},
                "base": {"ref": "main"},
                "state": "open",
            },
            "repository": {"full_name": "org/repo"},
        }
        event = await adapter.parse_webhook_event(payload)
        assert event is not None
        assert event.platform == PlatformType.GITHUB
        assert event.mr_iid == "42"
        assert event.action == "opened"

    @pytest.mark.asyncio
    async def test_github_ignores_non_pr_events(self):
        adapter = GitHubAdapter(token="test")
        payload = {"action": "opened", "issue": {"id": 1}}
        event = await adapter.parse_webhook_event(payload)
        assert event is None

    @pytest.mark.asyncio
    async def test_gitlab_parse_mr_open(self):
        adapter = GitLabAdapter(token="test")
        payload = {
            "object_kind": "merge_request",
            "object_attributes": {
                "id": 100,
                "iid": 5,
                "action": "open",
                "state": "opened",
                "updated_at": "2025-01-01T00:00:00Z",
            },
            "project": {"id": "20"},
        }
        event = await adapter.parse_webhook_event(payload)
        assert event is not None
        assert event.platform == PlatformType.GITLAB
        assert event.action == "opened"

    @pytest.mark.asyncio
    async def test_gitlab_ignores_push_events(self):
        adapter = GitLabAdapter(token="test")
        payload = {"object_kind": "push"}
        event = await adapter.parse_webhook_event(payload)
        assert event is None

    @pytest.mark.asyncio
    async def test_gitee_parse_pr_open(self):
        adapter = GiteeAdapter(token="test")
        payload = {
            "action": "open",
            "pull_request": {
                "id": 50,
                "number": 10,
            },
            "repository": {"full_name": "org/repo"},
        }
        event = await adapter.parse_webhook_event(payload)
        assert event is not None
        assert event.platform == PlatformType.GITEE
        assert event.action == "opened"
