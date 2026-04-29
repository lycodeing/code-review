"""LLM 配置 API 端点测试。"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from code_review.api.llm_config import router
from code_review.schemas.llm_config import TestConnectionResponse


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    mock_config = MagicMock()
    mock_config.server.secret_key = "test-secret"

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    app.state.config = mock_config
    app.state.session_factory = MagicMock(return_value=mock_cm)
    return app


@pytest.fixture
def app():
    return _make_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class TestTestExistingConnection:
    """测试 POST /{config_id}/test 端点。"""

    async def test_config_not_found_returns_404(self, client):
        config_id = uuid.uuid4()
        with patch("code_review.api.llm_config.LLMConfigService") as MockSvc:
            svc_instance = AsyncMock()
            svc_instance.get_config.return_value = None
            MockSvc.return_value = svc_instance

            resp = await client.post(f"/api/v1/llm-configs/{config_id}/test")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "配置不存在"

    async def test_decrypt_failure_returns_500(self, client):
        config_id = uuid.uuid4()
        mock_config = MagicMock()
        mock_config.api_key = "encrypted-key"
        mock_config.model_name = "gpt-4"
        mock_config.api_base = None

        with patch("code_review.api.llm_config.LLMConfigService") as MockSvc:
            svc_instance = AsyncMock()
            svc_instance.get_config.return_value = mock_config
            svc_instance.decrypt_api_key.side_effect = Exception("解密失败")
            MockSvc.return_value = svc_instance

            resp = await client.post(f"/api/v1/llm-configs/{config_id}/test")

        assert resp.status_code == 500
        assert resp.json()["detail"] == "API Key 解密失败"

    async def test_success_calls_do_test_with_real_key(self, client):
        config_id = uuid.uuid4()
        mock_config = MagicMock()
        mock_config.api_key = "encrypted-key"
        mock_config.model_name = "gpt-4"
        mock_config.api_base = "https://api.openai.com/v1"

        expected = TestConnectionResponse(success=True, message="连接成功", response_time_ms=42.0, model_info="gpt-4")

        with patch("code_review.api.llm_config.LLMConfigService") as MockSvc, \
             patch("code_review.api.llm_config._do_test_connection", return_value=expected) as mock_do_test:
            svc_instance = AsyncMock()
            svc_instance.get_config.return_value = mock_config
            svc_instance.decrypt_api_key.return_value = "real-api-key"
            MockSvc.return_value = svc_instance

            resp = await client.post(f"/api/v1/llm-configs/{config_id}/test")

        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mock_do_test.assert_awaited_once_with(
            model_name="gpt-4",
            api_key="real-api-key",
            api_base="https://api.openai.com/v1",
        )
