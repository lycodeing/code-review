"""公共 HTTP 客户端基类，封装重试、速率限制、错误处理。"""

import asyncio
import logging
from abc import ABC

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from code_review.core.platform import PlatformAdapter

logger = logging.getLogger(__name__)


class PlatformError(Exception):
    """平台 API 调用异常。"""

    def __init__(self, platform: str, status_code: int, message: str):
        self.platform = platform
        self.status_code = status_code
        self.message = message
        super().__init__(f"[{platform}] HTTP {status_code}: {message}")


class RateLimitError(PlatformError):
    """速率限制异常。"""
    def __init__(self, platform: str, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(platform, 429, f"Rate limited, retry after {retry_after}s")


class BasePlatformAdapter(PlatformAdapter, ABC):
    """平台适配器公共基类，提供 HTTP 请求和错误处理基础设施。"""

    def __init__(self, base_url: str, timeout: int = 30):
        self._base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None
        self._timeout = timeout

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
                headers=self._default_headers(),
            )
        return self._client

    def _default_headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, RateLimitError, PlatformError)),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
        headers: dict | None = None,
    ) -> dict | list:
        """发送 HTTP 请求，带重试和错误处理。"""
        client = await self._get_client()
        merged_headers = {**client.headers, **(headers or {})}

        response = await client.request(
            method, url, params=params, json=json, headers=merged_headers
        )

        # 速率限制处理
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "60"))
            logger.warning(
                "%s rate limited, retry after %ds", self.platform_type.value, retry_after
            )
            raise RateLimitError(self.platform_type.value, retry_after)

        # 服务端错误触发重试
        if response.status_code >= 500:
            raise PlatformError(
                self.platform_type.value, response.status_code, response.text
            )

        # 客户端错误不重试
        if response.status_code >= 400:
            raise PlatformError(
                self.platform_type.value, response.status_code, response.text
            )

        if response.status_code == 204:
            return {}

        return response.json()

    async def _get_all_pages(
        self,
        url: str,
        *,
        params: dict | None = None,
        page_size: int = 100,
    ) -> list[dict]:
        """自动分页获取所有结果。"""
        all_items: list[dict] = []
        page = 1
        params = dict(params or {})
        params["per_page"] = page_size

        while True:
            params["page"] = page
            data = await self._request("GET", url, params=params)

            if isinstance(data, list):
                all_items.extend(data)
                if len(data) < page_size:
                    break
                page += 1
            else:
                break

        return all_items

    async def close(self) -> None:
        """关闭 HTTP 客户端。"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def publish_comments_batch(
        self,
        project_id: str,
        mr_iid: str,
        comments: list,
    ) -> list[str]:
        """默认逐条发布，子类可覆盖。"""
        ids = []
        for comment in comments:
            cid = await self.publish_comment(project_id, mr_iid, comment)
            ids.append(cid)
        return ids
