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
        data = await self._get_all_pages(
            f"/repos/{owner}/{repo}/pulls/{mr_iid}/files",
            params=self._with_token(),
        )
        changes = []
        for f in data:
            status_map = {"added": "added", "modified": "modified", "removed": "removed", "renamed": "renamed"}
            # Gitee API 返回 patch 可能是 dict（包含 diff 键）或 str
            raw_patch = f.get("patch", "")
            if isinstance(raw_patch, dict):
                patch_text = raw_patch.get("diff", "")
            else:
                patch_text = raw_patch if isinstance(raw_patch, str) else ""
            changes.append(FileChange(
                path=f["filename"],
                old_path=f.get("previous_filename"),
                added=f.get("additions", 0),
                deleted=f.get("deletions", 0),
                status=status_map.get(f.get("status", "modified"), "modified"),
                diff=patch_text,
                patch=patch_text,
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
        data = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls/{mr_iid}/comments",
            params=self._with_token(),
            json={"body": comment.body},
        )
        return str(data.get("id", ""))

    async def publish_comments_batch(
        self,
        project_id: str,
        mr_iid: str,
        comments: list,
    ) -> list[str]:
        """将所有评审意见按严重级别分组，格式化为 Markdown PR 评论。"""
        owner, repo = self._parse_project_id(project_id)

        SEVERITY_CONFIG = [
            ("critical", "🔴 Critical", "必须修复"),
            ("warning", "🟡 Warning", "建议修复"),
            ("suggestion", "🔵 Suggestion", "优化建议"),
            ("info", "ℹ️ Info", "信息提示"),
        ]

        # 按严重级别分组
        groups: dict[str, list] = {}
        for c in comments:
            groups.setdefault(c.severity, []).append(c)

        # ---- 标题 + 统计摘要 ----
        parts = ["## 🔍 AI Code Review\n"]
        stats = []
        total = len(comments)
        for sev, label, _ in SEVERITY_CONFIG:
            n = len(groups.get(sev, []))
            if n:
                stats.append(f"{label} {n}")
        if stats:
            parts.append(f"> 📊 **共 {total} 条意见** — {' | '.join(stats)}\n")
        parts.append("---")

        # ---- 按类型分组输出 ----
        for sev, label, desc in SEVERITY_CONFIG:
            group = groups.get(sev)
            if not group:
                continue
            parts.append(f"\n### {label}（{desc}）\n")
            for idx, c in enumerate(group, 1):
                # 文件 + 行号定位
                if c.position:
                    parts.append(
                        f"\n**{idx}. 📄 `{c.position.path}` L{c.position.line}**\n"
                    )
                # 评论内容（含建议修复）
                parts.append(f"{c.body}\n")
            parts.append("\n---")

        body = "\n".join(parts)

        data = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls/{mr_iid}/comments",
            params=self._with_token(),
            json={"body": body},
        )
        return [str(data.get("id", ""))]

    # ---- Webhook 处理 ----
    _webhook_secret: str = ""

    def set_webhook_secret(self, secret: str) -> None:
        self._webhook_secret = secret

    async def verify_webhook_signature(
        self, payload: bytes, signature: str, timestamp: str = ""
    ) -> bool:
        """Gitee Webhook 签名验证。

        Gitee 签名算法（官方文档）：
        1. sign_str = timestamp + "\\n" + webhook_secret
        2. token = Base64(HMAC-SHA256(sign_str, webhook_secret))

        同时兼容直接 token 比对模式（明文密码方式）。
        """
        if not self._webhook_secret:
            logger.warning("Gitee webhook_secret not configured, skipping verification")
            return True

        if not signature:
            return False

        # 方式1：HMAC-SHA256 签名验证（Gitee 密钥签名方式）
        if timestamp:
            import base64
            sign_str = timestamp + "\n" + self._webhook_secret
            expected = base64.b64encode(
                hmac.new(
                    self._webhook_secret.encode("utf-8"),
                    sign_str.encode("utf-8"),
                    hashlib.sha256,
                ).digest()
            ).decode("utf-8")
            if hmac.compare_digest(expected, signature):
                return True

        # 方式2：直接 token 比对（明文密码方式）
        if hmac.compare_digest(self._webhook_secret, signature):
            return True

        return False

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
        # Gitee 的 updated_at 在 pull_request 对象内
        updated_at = pr.get("updated_at", "") or pr.get("created_at", "")
        event_id = f"gitee-{pr.get('id', '')}-{action}-{updated_at}"

        # 提取 MR 基本信息
        user = pr.get("user", {})
        mr_author = user.get("login", "") or user.get("name", "")
        mr_url = pr.get("html_url", "") or pr.get("url", "")

        return WebhookEvent(
            platform=PlatformType.GITEE,
            project_id=project_id,
            mr_id=str(pr.get("id", "")),
            mr_iid=str(pr.get("number", "")),
            action=action_map.get(action, action),
            event_id=event_id,
            mr_title=pr.get("title"),
            mr_author=mr_author,
            mr_url=mr_url,
            source_branch=pr.get("head", {}).get("ref") or pr.get("head", {}).get("label"),
            target_branch=pr.get("base", {}).get("ref") or pr.get("base", {}).get("label"),
            raw_payload=payload,
        )

    async def create_commit(
        self,
        project_id: str,
        mr_iid: str,
        file_path: str,
        content: str,
        commit_message: str,
        branch: str,
    ) -> str:
        """创建单文件 commit 并返回 commit SHA。"""
        import base64
        owner, repo = self._parse_project_id(project_id)

        # 先获取当前文件 SHA（如果文件存在）
        file_sha = None
        try:
            data = await self._request(
                "GET",
                f"/repos/{owner}/{repo}/contents/{file_path}",
                params=self._with_token({"ref": branch}),
            )
            file_sha = data.get("sha")
        except Exception:
            pass  # 文件不存在，新建

        # Base64 编码内容
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        payload = {
            "message": commit_message,
            "content": content_b64,
            "branch": branch,
        }
        if file_sha:
            payload["sha"] = file_sha

        data = await self._request(
            "PUT",
            f"/repos/{owner}/{repo}/contents/{file_path}",
            params=self._with_token(),
            json=payload,
        )
        commit_sha = data.get("commit", {}).get("sha")
        if not commit_sha:
            raise Exception(f"Gitee commit 创建失败: {data}")
        return commit_sha

    async def health_check(self) -> bool:
        try:
            await self._request("GET", "/user", params=self._with_token())
            return True
        except Exception:
            return False
