"""GitHub 平台适配器。"""

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


class GitHubAdapter(BasePlatformAdapter):
    """GitHub 平台适配器。

    认证方式：Bearer Token（Personal Access Token 或 GitHub App Token）。
    Webhook 签名：HMAC-SHA256（X-Hub-Signature-256）。
    """

    def __init__(self, token: str, api_url: str = "https://api.github.com"):
        super().__init__(api_url)
        self._token = token

    @property
    def platform_type(self) -> PlatformType:
        return PlatformType.GITHUB

    def _default_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        }

    # ---- 解析 project_id ----
    @staticmethod
    def _parse_project_id(project_id: str) -> tuple[str, str]:
        """将 owner/repo 格式拆分。"""
        parts = project_id.split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"GitHub project_id must be 'owner/repo', got: {project_id}")
        return parts[0], parts[1]

    # ---- MR/PR 操作 ----
    async def get_mr_info(self, project_id: str, mr_iid: str) -> MRInfo:
        owner, repo = self._parse_project_id(project_id)
        data = await self._request(
            "GET", f"/repos/{owner}/{repo}/pulls/{mr_iid}"
        )
        state_map = {"open": MRState.OPEN, "closed": MRState.CLOSED, "merged": MRState.MERGED}
        return MRInfo(
            platform=PlatformType.GITHUB,
            project_id=project_id,
            mr_id=str(data["id"]),
            mr_iid=str(data["number"]),
            title=data["title"],
            description=data.get("body") or "",
            author=data["user"]["login"],
            source_branch=data["head"]["ref"],
            target_branch=data["base"]["ref"],
            state=state_map.get(data["state"], MRState.OPEN),
            url=data["url"],
            web_url=data["html_url"],
        )

    async def get_mr_changes(self, project_id: str, mr_iid: str) -> list[FileChange]:
        owner, repo = self._parse_project_id(project_id)
        files = await self._get_all_pages(
            f"/repos/{owner}/{repo}/pulls/{mr_iid}/files"
        )
        changes = []
        for f in files:
            status_map = {"added": "added", "modified": "modified", "removed": "removed", "renamed": "renamed"}
            changes.append(FileChange(
                path=f["filename"],
                old_path=f.get("previous_filename"),
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
                params={"ref": ref},
            )
            # GitHub 返回 content 字段为 base64 编码
            import base64
            return base64.b64decode(data["content"]).decode("utf-8")
        except Exception as e:
            logger.warning("Failed to get file %s@%s: %s", file_path, ref, e)
            return None

    async def get_commits(self, project_id: str, mr_iid: str) -> list[CommitInfo]:
        owner, repo = self._parse_project_id(project_id)
        data = await self._get_all_pages(
            f"/repos/{owner}/{repo}/pulls/{mr_iid}/commits"
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

        if comment.position:
            # 行内评论 -> 创建 review comment
            body = self._format_comment_body(comment)
            payload: dict = {
                "body": body,
                "path": comment.position.path,
                "line": comment.position.line,
                "side": comment.position.side,
            }
            if comment.position.old_line:
                payload["start_line"] = comment.position.old_line
            data = await self._request(
                "POST",
                f"/repos/{owner}/{repo}/pulls/{mr_iid}/comments",
                json=payload,
            )
        else:
            # 通用评论
            data = await self._request(
                "POST",
                f"/repos/{owner}/{repo}/issues/{mr_iid}/comments",
                json={"body": comment.body},
            )
        return str(data.get("id", ""))

    async def publish_comments_batch(
        self, project_id: str, mr_iid: str, comments: list[PublishComment]
    ) -> list[str]:
        """利用 GitHub Pull Request Review API 批量发布行内评论。"""
        owner, repo = self._parse_project_id(project_id)

        inline_comments = [c for c in comments if c.position]
        general_comments = [c for c in comments if not c.position]

        review_id = None
        comment_ids = []

        if inline_comments:
            # 创建 pending review 批量提交行内评论
            review_comments = []
            for c in inline_comments:
                rc: dict = {
                    "path": c.position.path,
                    "body": self._format_comment_body(c),
                    "line": c.position.line,
                    "side": c.position.side,
                }
                if c.position.old_line:
                    rc["start_line"] = c.position.old_line
                review_comments.append(rc)

            data = await self._request(
                "POST",
                f"/repos/{owner}/{repo}/pulls/{mr_iid}/reviews",
                json={
                    "body": "",
                    "event": "COMMENT",
                    "comments": review_comments,
                },
            )
            review_id = data.get("id")

        # 通用评论逐条发布
        for c in general_comments:
            cid = await self.publish_comment(project_id, mr_iid, c)
            comment_ids.append(cid)

        return comment_ids

    @staticmethod
    def _format_comment_body(comment: PublishComment) -> str:
        """格式化评论内容，附加严重程度标签。"""
        severity_emoji = {
            "critical": "🔴",
            "warning": "🟡",
            "suggestion": "🔵",
            "info": "ℹ️",
        }
        emoji = severity_emoji.get(comment.severity, "")
        label = comment.severity.upper()
        return f"{emoji} **[{label}]** {comment.body}"

    # ---- Webhook 处理 ----
    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """验证 GitHub Webhook HMAC-SHA256 签名。"""
        if not self._webhook_secret:
            logger.warning("GitHub webhook_secret not configured, skipping verification")
            return True
        expected = "sha256=" + hmac.new(
            self._webhook_secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    _webhook_secret: str = ""

    def set_webhook_secret(self, secret: str) -> None:
        self._webhook_secret = secret

    async def parse_webhook_event(self, payload: dict) -> WebhookEvent | None:
        """解析 GitHub Webhook 事件。"""
        # 仅处理 pull_request 事件
        if payload.get("action") not in ("opened", "synchronize", "reopened", "closed"):
            return None

        pr = payload.get("pull_request")
        if not pr:
            return None

        repo = payload.get("repository", {})
        project_id = repo.get("full_name", "")

        # GitHub 没有 delivery_id 在 payload 中，从 headers 获取（API 层注入）
        event_id = payload.get("delivery_id", "") or str(pr.get("id", ""))

        action_map = {"synchronize": "synchronize", "reopened": "opened"}
        action = action_map.get(payload["action"], payload["action"])

        # 提取 MR 基本信息
        user = pr.get("user", {})
        mr_author = user.get("login", "")
        mr_url = pr.get("html_url", "") or pr.get("url", "")

        return WebhookEvent(
            platform=PlatformType.GITHUB,
            project_id=project_id,
            mr_id=str(pr["id"]),
            mr_iid=str(pr["number"]),
            action=action,
            event_id=event_id,
            mr_title=pr.get("title"),
            mr_author=mr_author,
            mr_url=mr_url,
            raw_payload=payload,
        )

    async def health_check(self) -> bool:
        try:
            await self._request("GET", "/user")
            return True
        except Exception:
            return False
