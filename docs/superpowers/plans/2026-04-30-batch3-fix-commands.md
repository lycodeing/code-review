# Batch 3: 一键修复 + 命令系统 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现评审建议一键应用为 commit，以及在 PR 评论中通过命令触发不同评审操作。

**Architecture:** 一键修复扩展 `PlatformAdapter` 新增 `create_commit()` 抽象方法，三个平台适配器各自实现。命令系统新增 `CommandRouter` 解析命令、`CommandHandler` 执行命令，扩展 Webhook 处理 comment 类型事件。

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy async, httpx, LangChain

---

## Feature E: P1-1 一键修复 / 代码建议应用

### 文件结构

| 操作 | 文件路径 | 职责 |
|------|---------|------|
| Create | `apps/backend/migrations/add_suggestion_applied.sql` | review_comments 新增字段 |
| Modify | `apps/backend/src/code_review/models/db.py:149-169` | ReviewComment 新增 applied 字段 |
| Modify | `apps/backend/src/code_review/core/platform.py` | PlatformAdapter 新增 create_commit 抽象方法 |
| Modify | `apps/backend/src/code_review/adapters/github.py` | GitHub 实现 create_commit |
| Modify | `apps/backend/src/code_review/adapters/gitlab.py` | GitLab 实现 create_commit |
| Modify | `apps/backend/src/code_review/adapters/gitee.py` | Gitee 实现 create_commit |
| Create | `apps/backend/src/code_review/api/suggestions.py` | 建议应用 API |
| Modify | `apps/backend/src/code_review/api/app.py` | 注册路由 |

### Task 1: 数据库迁移 — review_comments 新增 applied 字段

**Files:**
- Create: `apps/backend/migrations/add_suggestion_applied.sql`

- [ ] **Step 1: 创建迁移脚本**

```sql
-- apps/backend/migrations/add_suggestion_applied.sql
-- P1-1: 一键修复 — review_comments 新增 applied 相关字段

ALTER TABLE review_comments ADD COLUMN IF NOT EXISTS applied BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE review_comments ADD COLUMN IF NOT EXISTS applied_at TIMESTAMPTZ;
ALTER TABLE review_comments ADD COLUMN IF NOT EXISTS applied_commit_sha VARCHAR(64);
```

- [ ] **Step 2: ORM 模型同步**

在 `models/db.py` 的 `ReviewComment` 类（约行 162 `feedback` 字段后）添加：

```python
    applied = Column(Boolean, nullable=False, default=False, comment="是否已应用建议")
    applied_at = Column(DateTime(timezone=True), nullable=True, comment="应用时间")
    applied_commit_sha = Column(String(64), nullable=True, comment="应用后的 commit SHA")
```

- [ ] **Step 3: 执行迁移并验证**

```bash
psql -U postgres -d code_review -f apps/backend/migrations/add_suggestion_applied.sql
cd apps/backend && python -c "from code_review.models.db import ReviewComment; print('OK')"
```

- [ ] **Step 4: 提交**

```bash
git add apps/backend/migrations/add_suggestion_applied.sql apps/backend/src/code_review/models/db.py
git commit -m "feat: review_comments 新增 applied/applied_at/applied_commit_sha 字段"
```

---

### Task 2: PlatformAdapter 新增 create_commit 抽象方法

**Files:**
- Modify: `apps/backend/src/code_review/core/platform.py:98-164`

- [ ] **Step 1: 在 PlatformAdapter 类中新增抽象方法**

在 `platform.py` 的 `PlatformAdapter` 类中（`health_check` 方法之前，约行 161）添加：

```python
    @abstractmethod
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
```

- [ ] **Step 2: 验证语法**

```bash
cd apps/backend && python -m py_compile src/code_review/core/platform.py
```

- [ ] **Step 3: 提交**

```bash
git add apps/backend/src/code_review/core/platform.py
git commit -m "feat: PlatformAdapter 新增 create_commit 抽象方法"
```

---

### Task 3: 三个平台适配器实现 create_commit

**Files:**
- Modify: `apps/backend/src/code_review/adapters/github.py`
- Modify: `apps/backend/src/code_review/adapters/gitlab.py`
- Modify: `apps/backend/src/code_review/adapters/gitee.py`

- [ ] **Step 1: GitHub 适配器实现**

在 `github.py` 的 `GithubAdapter` 类中添加：

```python
    async def create_commit(
        self,
        project_id: str,
        mr_iid: str,
        file_path: str,
        content: str,
        commit_message: str,
        branch: str,
    ) -> str:
        import base64
        url = f"{self._api_base}/repos/{project_id}/contents/{file_path}"
        headers = self._headers()

        # 获取当前文件 SHA
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, headers=headers, params={"ref": branch})
            if resp.status_code != 200:
                raise RuntimeError(f"获取文件 SHA 失败: {resp.status_code} {resp.text}")
            current_sha = resp.json().get("sha")

        # 提交更新
        body = {
            "message": commit_message,
            "content": base64.b64encode(content.encode()).decode(),
            "sha": current_sha,
            "branch": branch,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.put(url, headers=headers, json=body)
            if resp.status_code not in (200, 201):
                raise RuntimeError(f"提交失败: {resp.status_code} {resp.text}")
            return resp.json()["commit"]["sha"]
```

确保文件顶部有 `import httpx`。

- [ ] **Step 2: GitLab 适配器实现**

在 `gitlab.py` 的 `GitlabAdapter` 类中添加：

```python
    async def create_commit(
        self,
        project_id: str,
        mr_iid: str,
        file_path: str,
        content: str,
        commit_message: str,
        branch: str,
    ) -> str:
        import base64
        encoded_path = httpx._content.encode_multipart_formdata  # 不用这个
        # URL 编码文件路径
        from urllib.parse import quote
        encoded_path = quote(file_path, safe="")

        url = f"{self._api_base}/api/v4/projects/{project_id}/repository/files/{encoded_path}"
        headers = self._headers()

        body = {
            "branch": branch,
            "content": content,
            "commit_message": commit_message,
            "encoding": "text",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.put(url, headers=headers, json=body)
            if resp.status_code not in (200, 201):
                raise RuntimeError(f"提交失败: {resp.status_code} {resp.text}")
            return resp.json().get("blob_id", "")
```

- [ ] **Step 3: Gitee 适配器实现**

在 `gitee.py` 的 `GiteeAdapter` 类中添加：

```python
    async def create_commit(
        self,
        project_id: str,
        mr_iid: str,
        file_path: str,
        content: str,
        commit_message: str,
        branch: str,
    ) -> str:
        import base64
        url = f"{self._api_base}/api/v5/repos/{project_id}/contents/{file_path}"
        headers = self._headers()

        # 获取当前文件 SHA
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, headers=headers, params={"ref": branch})
            if resp.status_code != 200:
                raise RuntimeError(f"获取文件 SHA 失败: {resp.status_code} {resp.text}")
            current_sha = resp.json().get("sha")

        body = {
            "message": commit_message,
            "content": base64.b64encode(content.encode()).decode(),
            "sha": current_sha,
            "branch": branch,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.put(url, headers=headers, json=body)
            if resp.status_code not in (200, 201):
                raise RuntimeError(f"提交失败: {resp.status_code} {resp.text}")
            return resp.json().get("content", {}).get("sha", "")
```

- [ ] **Step 4: 验证语法**

```bash
cd apps/backend && python -m py_compile src/code_review/adapters/github.py src/code_review/adapters/gitlab.py src/code_review/adapters/gitee.py
```

- [ ] **Step 5: 提交**

```bash
git add apps/backend/src/code_review/adapters/
git commit -m "feat: GitHub/GitLab/Gitee 适配器实现 create_commit"
```

---

### Task 4: 建议应用 API

**Files:**
- Create: `apps/backend/src/code_review/api/suggestions.py`

- [ ] **Step 1: 实现建议应用 API**

```python
"""代码建议应用 API — 将评审建议直接提交为 commit。"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from code_review.models.db import ReviewComment, ReviewTask, CommentReply, Project
from code_review.infrastructure.adapter_factory import create_adapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/suggestions", tags=["suggestions"])


class ApplyResult(BaseModel):
    comment_id: str
    commit_sha: str
    applied_at: str


class BatchApplyRequest(BaseModel):
    comment_ids: list[str]


class BatchApplyResult(BaseModel):
    results: list[ApplyResult]
    failed: list[dict]


@router.post("/{comment_id}/apply")
async def apply_suggestion(comment_id: UUID, request: Request):
    """应用单条评审建议。"""
    session_factory = request.app.state.session_factory
    secret_key = request.app.state.config.server.secret_key

    async with session_factory() as session:
        comment = await session.get(ReviewComment, comment_id)
        if not comment:
            raise HTTPException(status_code=404, detail="评论不存在")

        if not comment.suggestion:
            raise HTTPException(status_code=400, detail="该评论没有代码建议")
        if comment.applied:
            raise HTTPException(status_code=400, detail="该建议已被应用")

        task = await session.get(ReviewTask, comment.task_id)
        if not task:
            raise HTTPException(status_code=404, detail="关联的评审任务不存在")

        project = await session.get(Project, task.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 获取平台配置并创建适配器
        from code_review.services.review_orchestrator import ReviewOrchestrator
        orchestrator = request.app.state.orchestrator
        platform_config = await orchestrator._get_platform_config(project.platform)
        if not platform_config:
            raise HTTPException(status_code=500, detail="平台配置缺失")

        adapter = create_adapter(
            platform=project.platform,
            platform_config=platform_config,
            project_webhook_secret=project.webhook_secret or "",
        )

        # 提取建议中的代码块
        suggestion_content = _extract_code_block(comment.suggestion)

        try:
            commit_sha = await adapter.create_commit(
                project_id=project.platform_project_id,
                mr_iid=task.mr_iid,
                file_path=comment.file_path,
                content=suggestion_content,
                commit_message=f"fix: 应用 AI 评审建议 ({comment.file_path}:{comment.line_start})",
                branch=task.source_branch or "main",
            )
        except Exception as e:
            logger.error("应用建议失败: %s", e)
            raise HTTPException(status_code=500, detail=f"提交失败: {e}")

        # 更新评论状态
        comment.applied = True
        comment.applied_at = datetime.now(timezone.utc)
        comment.applied_commit_sha = commit_sha

        # 记录系统回复
        reply = CommentReply(
            comment_id=comment.id,
            author="system",
            content=f"建议已应用，commit: `{commit_sha[:8]}`",
            source="system",
        )
        session.add(reply)
        await session.commit()

        return ApplyResult(
            comment_id=str(comment.id),
            commit_sha=commit_sha,
            applied_at=comment.applied_at.isoformat(),
        )


@router.post("/batch-apply")
async def batch_apply(body: BatchApplyRequest, request: Request):
    """批量应用多条建议。"""
    results: list[ApplyResult] = []
    failed: list[dict] = []

    for cid in body.comment_ids:
        try:
            result = await apply_suggestion(UUID(cid), request)
            results.append(result)
        except Exception as e:
            failed.append({"comment_id": cid, "error": str(e)})

    return BatchApplyResult(results=results, failed=failed)


def _extract_code_block(suggestion: str) -> str:
    """从建议文本中提取代码块内容。如果无代码块标记，返回原文。"""
    import re
    pattern = r"```(?:\w+)?\n(.*?)```"
    matches = re.findall(pattern, suggestion, re.DOTALL)
    if matches:
        return matches[0]
    return suggestion
```

- [ ] **Step 2: 在 app.py 注册路由**

在 `app.py` 导入区添加：

```python
from code_review.api.suggestions import router as suggestions_router
```

在路由注册区添加：

```python
    app.include_router(suggestions_router)
```

- [ ] **Step 3: 验证语法**

```bash
cd apps/backend && python -m py_compile src/code_review/api/suggestions.py src/code_review/api/app.py
```

- [ ] **Step 4: 提交**

```bash
git add apps/backend/src/code_review/api/suggestions.py apps/backend/src/code_review/api/app.py
git commit -m "feat: 实现代码建议应用 API（单条 + 批量）"
```

---

## Feature F: P1-2 命令系统扩展

### 文件结构

| 操作 | 文件路径 | 职责 |
|------|---------|------|
| Create | `apps/backend/src/code_review/services/command_router.py` | 命令解析器 |
| Create | `apps/backend/src/code_review/services/command_handler.py` | 命令处理器 |
| Modify | `apps/backend/src/code_review/api/webhook.py` | 支持 comment 事件 |
| Modify | `apps/backend/src/code_review/adapters/github.py` | 解析 comment 事件 |
| Modify | `apps/backend/src/code_review/adapters/gitlab.py` | 解析 comment 事件 |
| Modify | `apps/backend/src/code_review/adapters/gitee.py` | 解析 comment 事件 |
| Modify | `apps/backend/src/code_review/services/review_orchestrator.py:116-277` | 命令路由分支 |

### Task 5: 命令解析器

**Files:**
- Create: `apps/backend/src/code_review/services/command_router.py`

- [ ] **Step 1: 实现 CommandRouter**

```python
"""命令路由器 — 从 PR 评论中解析命令。"""

import logging

logger = logging.getLogger(__name__)


class CommandRouter:
    """从评论内容中解析命令。"""

    COMMANDS: dict[str, str] = {
        "/review": "review",
        "/describe": "describe",
        "/improve": "improve",
        "/analyze": "analyze",
    }

    def parse_command(self, comment_body: str) -> tuple[str, str] | None:
        """从评论内容中解析命令。返回 (command, args) 或 None。"""
        body = comment_body.strip().lower()
        for cmd_prefix, cmd_name in self.COMMANDS.items():
            if body.startswith(cmd_prefix):
                args = comment_body.strip()[len(cmd_prefix):].strip()
                logger.info("解析到命令: %s, 参数: %s", cmd_name, args)
                return cmd_name, args
        return None
```

- [ ] **Step 2: 提交**

```bash
git add apps/backend/src/code_review/services/command_router.py
git commit -m "feat: 实现命令解析器 CommandRouter"
```

---

### Task 6: 命令处理器

**Files:**
- Create: `apps/backend/src/code_review/services/command_handler.py`

- [ ] **Step 1: 实现 CommandHandler**

```python
"""命令处理器 — 执行不同类型的评审命令。"""

import logging
from collections import Counter

from code_review.services.command_router import CommandRouter
from code_review.services.rule_engine import get_rules_for_project, check_changes_against_rules
from code_review.core.platform import PublishComment

logger = logging.getLogger(__name__)


class CommandHandler:
    """命令处理器。"""

    def __init__(self, orchestrator):
        self._orchestrator = orchestrator

    async def handle_review(self, event, session_factory) -> None:
        """执行完整评审（同现有 Webhook 流程）。"""
        # 复用现有 process_webhook_event 逻辑
        await self._orchestrator.process_webhook_event(event)

    async def handle_describe(self, event, session_factory, adapter=None) -> None:
        """仅生成 PR 摘要。"""
        raw = event.raw_payload
        project_id = raw.get("project_id", "")
        mr_iid = raw.get("mr_iid", "")

        if not adapter or not project_id or not mr_iid:
            logger.warning("describe 命令缺少必要参数")
            return

        changes = await adapter.get_mr_changes(project_id, mr_iid)
        mr_info = await adapter.get_mr_info(project_id, mr_iid)

        file_list = sorted({c.path for c in changes})[:10]
        body = f"## PR 描述\n\n"
        body += f"**标题:** {mr_info.title}\n"
        body += f"**作者:** {mr_info.author}\n"
        body += f"**分支:** {mr_info.source_branch} → {mr_info.target_branch}\n\n"
        body += f"**变更文件（{len(changes)} 个）：**\n"
        for f in file_list:
            body += f"- `{f}`\n"

        await adapter.publish_comment(
            project_id, mr_iid, PublishComment(body=body, position=None)
        )

    async def handle_improve(self, event, session_factory) -> None:
        """生成改进建议（含代码建议）。复用评审流程但使用 improve 模板。"""
        raw = event.raw_payload
        raw["force_template"] = "improve_zh"
        await self._orchestrator.process_webhook_event(event)

    async def handle_analyze(self, event, session_factory, adapter=None) -> None:
        """仅运行规则引擎检查。"""
        raw = event.raw_payload
        project_id = raw.get("project_id", "")
        mr_iid = raw.get("mr_iid", "")
        db_project_id = raw.get("db_project_id")

        if not adapter or not db_project_id or not mr_iid:
            logger.warning("analyze 命令缺少必要参数")
            return

        from uuid import UUID
        changes = await adapter.get_mr_changes(project_id, mr_iid)

        async with session_factory() as session:
            rules = await get_rules_for_project(session, UUID(db_project_id))
            rule_comments = check_changes_against_rules(changes, rules)

        if rule_comments:
            body = "## 规则引擎检查结果\n\n"
            for rc in rule_comments:
                body += f"- **[{rc.severity.value}]** `{rc.file_path}:{rc.line_start}` — {rc.message}\n"
            await adapter.publish_comment(
                project_id, mr_iid, PublishComment(body=body, position=None)
            )
        else:
            await adapter.publish_comment(
                project_id, mr_iid,
                PublishComment(body="## 规则引擎检查结果\n\n未发现规则命中。", position=None)
            )
```

- [ ] **Step 2: 提交**

```bash
git add apps/backend/src/code_review/services/command_handler.py
git commit -m "feat: 实现命令处理器 CommandHandler"
```

---

### Task 7: Webhook 支持 comment 事件

**Files:**
- Modify: `apps/backend/src/code_review/api/webhook.py`
- Modify: 平台适配器的 `parse_webhook_event`

- [ ] **Step 1: 在 webhook.py 中添加 comment 事件处理**

在 `webhook.py` 的各平台 Webhook 处理函数中，添加对 comment 类型事件的支持。在 `github_webhook` 函数中（约行 17-59）添加：

```python
    # 处理 PR 评论事件
    if event_type == "issue_comment" and payload.get("action") == "created":
        comment_body = payload.get("comment", {}).get("body", "")
        # 过滤 bot 用户评论防止循环
        sender = payload.get("comment", {}).get("user", {}).get("login", "")
        if sender.endswith("[bot]") or sender == "github-actions[bot]":
            return {"status": "ignored", "reason": "bot comment"}
        from code_review.services.command_router import CommandRouter
        command = CommandRouter().parse_command(comment_body)
        if command:
            pr = payload.get("issue", {}).get("pull_request", {})
            repo = payload.get("repository", {})
            event = WebhookEvent(
                platform=PlatformType.GITHUB,
                action="command",
                project_id=f"{repo.get('owner', {}).get('login', '')}/{repo.get('name', '')}",
                mr_iid=str(pr.get("number", "")),
                raw_payload={
                    "command": command[0],
                    "args": command[1],
                    "project_id": f"{repo.get('owner', {}).get('login', '')}/{repo.get('name', '')}",
                    "mr_iid": str(pr.get("number", "")),
                    "comment_body": comment_body,
                },
            )
            orchestrator = request.app.state.orchestrator
            await orchestrator.process_webhook_event(event)
            return {"status": "command_received", "command": command[0]}
```

类似地，在 `gitlab_webhook`（约行 62-96）和 `gitee_webhook`（约行 98-154）中添加对应逻辑。

- [ ] **Step 2: 验证语法**

```bash
cd apps/backend && python -m py_compile src/code_review/api/webhook.py
```

- [ ] **Step 3: 提交**

```bash
git add apps/backend/src/code_review/api/webhook.py
git commit -m "feat: Webhook 支持 PR 评论命令触发（GitHub/GitLab/Gitee）"
```

---

### Task 8: 编排器命令路由分支

**Files:**
- Modify: `apps/backend/src/code_review/services/review_orchestrator.py:116-277`

- [ ] **Step 1: 在 process_webhook_event 中添加命令分支**

在 `review_orchestrator.py` 的 `process_webhook_event` 方法中，添加命令路由处理：

```python
        # 命令模式处理
        if event.action == "command":
            command = event.raw_payload.get("command")
            from code_review.services.command_handler import CommandHandler
            handler = CommandHandler(self)
            match command:
                case "review":
                    await handler.handle_review(event, self._session_factory)
                case "describe":
                    # describe 和 analyze 需要 adapter
                    project = await self._find_project(session, event)
                    if project:
                        platform_config = await self._get_platform_config(project.platform)
                        adapter = create_adapter(
                            platform=project.platform,
                            platform_config=platform_config,
                            project_webhook_secret=project.webhook_secret or "",
                        )
                        event.raw_payload["db_project_id"] = str(project.id)
                        await handler.handle_describe(event, self._session_factory, adapter)
                case "improve":
                    await handler.handle_improve(event, self._session_factory)
                case "analyze":
                    project = await self._find_project(session, event)
                    if project:
                        platform_config = await self._get_platform_config(project.platform)
                        adapter = create_adapter(
                            platform=project.platform,
                            platform_config=platform_config,
                            project_webhook_secret=project.webhook_secret or "",
                        )
                        event.raw_payload["db_project_id"] = str(project.id)
                        await handler.handle_analyze(event, self._session_factory, adapter)
            return None
```

这段代码需要插入在方法开头，找到项目之前。需要将 `_find_project` 和 `create_adapter` 确保可访问。

- [ ] **Step 2: 验证语法**

```bash
cd apps/backend && python -m py_compile src/code_review/services/review_orchestrator.py
```

- [ ] **Step 3: 提交**

```bash
git add apps/backend/src/code_review/services/review_orchestrator.py
git commit -m "feat: 编排器支持命令路由分支（review/describe/improve/analyze）"
```

---

## 验证清单

### 一键修复验证

- [ ] 应用建议后在 GitHub/GitLab 上检查是否有新 commit
- [ ] 重复应用同一条建议返回 400 错误
- [ ] `suggestion` 为空时返回 400 错误
- [ ] 应用后评论状态更新（applied=True）
- [ ] 应用后有系统回复记录 commit SHA

### 命令系统验证

- [ ] 在 PR 评论中输入 `/review` 触发完整评审
- [ ] `/describe` 仅生成摘要不运行规则引擎
- [ ] `/improve` 使用改进模板调用 LLM
- [ ] `/analyze` 仅运行规则引擎检查
- [ ] 无效命令不做任何操作
- [ ] bot 用户评论不触发（防止循环）
