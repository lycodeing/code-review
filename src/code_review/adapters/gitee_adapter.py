"""Gitee 平台适配器。"""

import hashlib
import hmac
import logging

from code_review.adapters.base import BasePlatformAdapter
from code_review.core.platform import (
    PlatformType,
    MRInfo,
    MRState,
    FileChange,
    CommitInfo,
    PublishComment,
    WebhookEvent,
)

logger = logging.getLogger(__name__)


class GiteeAdapter(BasePlatformAdapter):
    """Gitee 平台适配器。

    认证方式：Private Token（通过 access_token 参数或 Header）。
    Webhook 签名：HMAC-SHA256（X-Gitee-Token 或签名验证）。
    """

    def __init__(self, token: str, api_url: str = "https://gitee.com/api/v5"):
        super().__init__(api_url)
        self._token = token

    @property
    def platform_type(self) -> PlatformType:
        return PlatformType.GITEE

    def _default_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
        }

    def _with_token(self, params: dict | None = None) -> dict:
        """将 access_token 附加到查询参数（Gitee 风格）。"""
        p = dict(params or {})
        p["access_token"] = self._token
        return p

    @staticmethod
    def _parse_project_id(project_id: str) -> tuple[str, str]:
        parts = project_id.split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Gitee project_id must be 'owner/repo', got: {project_id}")
        return parts[0], parts[1]

    # ---- PR 操作 ----
    async def get_mr_info(self, project_id: str, mr_iid: str) -> MRInfo:
        owner, repo = self._parse_project_id(project_id)
        data = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{mr_iid}",
            params=self._with_token(),
        )
        state_map = {"open": MRState.OPEN, "closed": MRState.CLOSED, "merged": MRState.MERGED}
        return MRInfo(
            platform=PlatformType.GITEE,
            project_id=project_id,
            mr_id=str(data["id"]),
            mr_iid=str(data["number"]),
            title=data["title"],
            description=data.get("body") or "",
            author=data["user"]["login"],
            source_branch=data["head"]["ref"],
            target_branch=data["base"]["ref"],
            state=state_map.get(data["state"], MRState.OPEN),
            url=data.get("url", ""),
            web_url=data.get("html_url", ""),
        )

    async def get_mr_changes(self, project_id: str, mr_iid: str) -> list[FileChange]:
        owner, repo = self._parse_project_id(project_id)
        data = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{mr_iid}/files",
            params=self._with_token({"page": 1, "per_page": 100}),
        )
        changes = []
        for f in data:
            status_map = {"added": "added", "modified": "modified", "removed": "removed"}
            changes.append(FileChange(
                path=f["filename"],
                added=f.get("additions", 0),
                deleted=f.get("deletions", 0),
                status=status_map.get(f.get("status", "modified"), "modified"),
                diff=f.get("patch", ""),
                patch=f.get("patch", ""),
            ))
        return changes

    async def get_file_content(self, project_id: str, file_path: str, ref: str) -> str | None:
        owner, repo = self._parse_project_id(project_id)
        try:
            data = await self._request(
                "GET",
                f"/repos/{owner}/{repo}/contents/{file_path}",
                params=self._with_token({"ref": ref}),
            )
            import base64
            return base64.b64decode(data["content"]).decode("utf-8")
        except Exception as e:
            logger.warning("Failed to get file %s@%s: %s", file_path, ref, e)
            return None

    async def get_commits(self, project_id: str, mr_iid: str) -> list[CommitInfo]:
        owner, repo = self._parse_project_id(project_id)
        data = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{mr_iid}/commits",
            params=self._with_token(),
        )
        return [
            CommitInfo(
                sha=c["sha"],
                message=c["commit"]["message"],
                author=c["commit"]["author"]["name"],
                timestamp=c["commit"]["author"]["date"],
            )
            for c in data
        ]

    # ---- 评论发布 ----
    async def publish_comment(
        self, project_id: str, mr_iid: str, comment: PublishComment
    ) -> str:
        owner, repo = self._parse_project_id(project_id)
        body = self._format_comment_body(comment)

        if comment.position:
            payload = {
                "body": body,
                "path": comment.position.path,
                "line": comment.position.line,
                "side": comment.position.side,
            }
            data = await self._request(
                "POST",
                f"/repos/{owner}/{repo}/pulls/{mr_iid}/comments",
                params=self._with_token(),
                json=payload,
            )
        else:
            data = await self._request(
                "POST",
                f"/repos/{owner}/{repo}/pulls/{mr_iid}/comments",
                params=self._with_token(),
                json={"body": body},
            )
        return str(data.get("id", ""))

    @staticmethod
    def _format_comment_body(comment: PublishComment) -> str:
        severity_emoji = {
            "critical": "🔴", "warning": "🟡", "suggestion": "🔵", "info": "ℹ️",
        }
        emoji = severity_emoji.get(comment.severity, "")
        return f"{emoji} **[{comment.severity.upper()}]** {comment.body}"

    # ---- Webhook 处理 ----
    _webhook_secret: str = ""

    def set_webhook_secret(self, secret: str) -> None:
        self._webhook_secret = secret

    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Gitee 使用 X-Gitee-Token 或 HMAC-SHA256 签名。"""
        if not self._webhook_secret:
            logger.warning("Gitee webhook_secret not configured, skipping verification")
            return True
        # 优先尝试 HMAC-SHA256
        expected = hashlib.sha256(
            self._webhook_secret.encode() + payload
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def parse_webhook_event(self, payload: dict) -> WebhookEvent | None:
        action = payload.get("action")
        if action not in ("open", "update", "close", "merge"):
            return None

        pr = payload.get("pull_request")
        if not pr:
            return None

        repo = payload.get("repository", {})
        project_id = repo.get("full_name", "") or repo.get("path_with_namespace", "")

        action_map = {"open": "opened", "update": "updated", "close": "closed", "merge": "merged"}
        event_id = f"gitee-{pr.get('id', '')}-{action}-{payload.get('updated_at', '')}"

        return WebhookEvent(
            platform=PlatformType.GITEE,
            project_id=project_id,
            mr_id=str(pr.get("id", "")),
            mr_iid=str(pr.get("number", "")),
            action=action_map.get(action, action),
            event_id=event_id,
            raw_payload=payload,
        )

    async def health_check(self) -> bool:
        try:
            await self._request("GET", "/user", params=self._with_token())
            return True
        except Exception:
            return False
