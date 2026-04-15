"""配置模型测试。"""

import os
import pytest

from code_review.models.config import AppConfig, ReviewConfig


class TestAppConfig:
    """配置加载测试。"""

    def test_default_config(self):
        config = AppConfig()
        assert config.server.port == 8000
        assert config.review.comment_language == "zh"
        assert config.review.comment_mode == "detailed"
        assert config.review.max_comments_per_mr == 50
        assert "*.lock" in config.review.exclude_patterns

    def test_env_override(self):
        os.environ["CODE_REVIEW__SERVER__PORT"] = "9000"
        try:
            config = AppConfig()
            assert config.server.port == 9000
        finally:
            del os.environ["CODE_REVIEW__SERVER__PORT"]

    def test_review_config_defaults(self):
        config = ReviewConfig()
        assert config.comment_language in ("zh", "en")
        assert config.max_comments_per_mr > 0
        assert config.severity_threshold_for_summary > 0

    def test_platforms_disabled_by_default(self):
        config = AppConfig()
        assert not config.feishu.enabled
        assert not config.dingtalk.enabled
        assert not config.email.enabled
