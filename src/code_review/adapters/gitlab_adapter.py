"""GitLab 平台适配器。"""

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


class GitLabAdapter(BasePlatformAdapter):
    """GitLab 平台适配器。

    认证方式：Private Token 或 OAuth2 Bearer Token。
    Webhook 签名：Token 验证（X-Gitlab-Token）。
    """

    def __init__(self, token: str, api_url: str = "https://gitlab.com/api/v4"):
        super().__init__(api_url)
        self._token = token

    @property
    def platform_type(self) -> PlatformType:
        return PlatformType.GITLAB

    def _default_headers(self) -> dict[str, str]:
        return {
            "PRIVATE-TOKEN": self._token,
            "Content-Type": "application/json",
        }

    # ---- MR 操作 ----
    async def get_mr_info(self, project_id: str, mr_iid: str) -> MRInfo:
        data = await self._request(
            "GET", f"/projects/{_url_encode(project_id)}/merge_requests/{mr_iid}"
        )
        state_map = {
            "opened": MRState.OPEN, "closed": MRState.CLOSED, "merged": MRState.MERGED,
        }
        return MRInfo(
            platform=PlatformType.GITLAB,
            project_id=project_id,
            mr_id=str(data["id"]),
            mr_iid=str(data["iid"]),
            title=data["title"],
            description=data.get("description") or "",
            author=data["author"]["username"],
            source_branch=data["source_branch"],
            target_branch=data["target_branch"],
            state=state_map.get(data["state"], MRState.OPEN),
            url=data.get("web_url", ""),
            web_url=data.get("web_url", ""),
        )

    async def get_mr_changes(self, project_id: str, mr_iid: str) -> list[FileChange]:
        data = await self._request(
            "GET",
            f"/projects/{_url_encode(project_id)}/merge_requests/{mr_iid}/changes",
        )
        changes = []
        for f in data.get("changes", []):
            status = "modified"
            if f.get("new_file"):
                status = "added"
            elif f.get("deleted_file"):
                status = "removed"
            elif f.get("renamed_file"):
                status = "renamed"

            diff_text = f.get("diff", "")
            lines = diff_text.split("\n") if diff_text else []
            added = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
            deleted = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))

            changes.append(FileChange(
                path=f.get("new_path", ""),
                old_path=f.get("old_path"),
                added=added,
                deleted=deleted,
                status=status,
                diff=diff_text,
            ))
        return changes

    async def get_file_content(self, project_id: str, file_path: str, ref: str) -> str | None:
        import urllib.parse
        encoded_path = urllib.parse.quote(file_path, safe="")
        try:
            data = await self._request(
                "GET",
                f"/projects/{_url_encode(project_id)}/repository/files/{encoded_path}",
                params={"ref": ref},
            )
            import base64
            return base64.b64decode(data["content"]).decode("utf-8")
        except Exception as e:
            logger.warning("Failed to get file %s@%s: %s", file_path, ref, e)
            return None

    async def get_commits(self, project_id: str, mr_iid: str) -> list[CommitInfo]:
        data = await self._get_all_pages(
            f"/projects/{_url_encode(project_id)}/merge_requests/{mr_iid}/commits"
        )
        return [
            CommitInfo(
                sha=c["id"],
                message=c["message"],
                author=c["author_name"],
                timestamp=c["authored_date"],
            )
            for c in data
        ]

    # ---- 评论发布 ----
    async def publish_comment(
        self, project_id: str, mr_iid: str, comment: PublishComment
    ) -> str:
        encoded_pid = _url_encode(project_id)

        if comment.position:
            # GitLab 行内评论需要 position 参数
            body = self._format_comment_body(comment)
            payload: dict = {
                "body": body,
                "position": {
                    "base_sha": "",  # 由服务层填充
                    "head_sha": "",
                    "start_sha": "",
                    "position_type": "text",
                    "new_path": comment.position.path,
                    "new_line": comment.position.line,
                },
            }
            if comment.position.old_line:
                payload["position"]["old_path"] = comment.position.path
                payload["position"]["old_line"] = comment.position.old_line
            data = await self._request(
                "POST",
                f"/projects/{encoded_pid}/merge_requests/{mr_iid}/discussions",
                json=payload,
            )
        else:
            data = await self._request(
                "POST",
                f"/projects/{encoded_pid}/merge_requests/{mr_iid}/notes",
                json={"body": comment.body},
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
        """GitLab 使用 X-Gitlab-Token 直接比对。"""
        if not self._webhook_secret:
            logger.warning("GitLab webhook_secret not configured, skipping verification")
            return True
        return hmac.compare_digest(self._webhook_secret, signature)

    async def parse_webhook_event(self, payload: dict) -> WebhookEvent | None:
        object_kind = payload.get("object_kind")
        if object_kind != "merge_request":
            return None

        attrs = payload.get("object_attributes", {})
        state = attrs.get("state", "")
        action = attrs.get("action", "")

        # 仅处理打开和更新事件
        action_map = {
            "open": "opened", "reopen": "opened", "update": "updated", "merge": "merged",
            "close": "closed",
        }
        mapped_action = action_map.get(action)
        if not mapped_action:
            return None

        project = payload.get("project", {})
        # event_id 使用 merge request 的全局 ID + action + updated_at 构造
        event_id = f"gl-{attrs.get('id', '')}-{action}-{attrs.get('updated_at', '')}"

        return WebhookEvent(
            platform=PlatformType.GITLAB,
            project_id=str(project.get("id", "")),
            mr_id=str(attrs.get("id", "")),
            mr_iid=str(attrs.get("iid", "")),
            action=mapped_action,
            event_id=event_id,
            raw_payload=payload,
        )

    async def health_check(self) -> bool:
        try:
            await self._request("GET", "/user")
            return True
        except Exception:
            return False


def _url_encode(project_id: str) -> str:
    """GitLab 项目 ID 需要URL 编码（owner/repo -> owner%2Frepo）。"""
    import urllib.parse
    if "/" in project_id:
        return urllib.parse.quote(project_id, safe="")
    return project_id
