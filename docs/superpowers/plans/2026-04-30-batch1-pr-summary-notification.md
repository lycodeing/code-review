# Batch 1: PR 摘要自动生成 + 通知渠道增强 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 PR 摘要自动发布和企业微信/Slack 通知渠道，快速交付两个独立的高价值功能。

**Architecture:** PR 摘要在现有评审流水线的评论发布步骤后、通知发送前插入，用已有数据组装（零额外 LLM 调用）。通知增强复用现有 `NotificationChannel` 抽象，新增两个渠道实现类并注册到 `CHANNEL_REGISTRY`。

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy async, httpx, PostgreSQL

---

## Feature A: P0-2 PR 摘要自动生成

### 文件结构

| 操作 | 文件路径 | 职责 |
|------|---------|------|
| Create | `apps/backend/migrations/add_pr_description.sql` | 数据库迁移脚本 |
| Modify | `apps/backend/src/code_review/models/db.py:56-118` | ReviewTask 模型新增字段 |
| Modify | `apps/backend/src/code_review/services/review_orchestrator.py:472-520` | 评论发布后插入摘要生成 |
| Modify | `apps/backend/migrations/add_system_settings.sql` 或种子数据 | 新增系统配置项 |

### Task 1: 数据库迁移 — review_tasks 表新增字段

**Files:**
- Create: `apps/backend/migrations/add_pr_description.sql`

- [ ] **Step 1: 创建迁移脚本**

```sql
-- apps/backend/migrations/add_pr_description.sql
-- P0-2: PR 摘要自动生成 — review_tasks 表新增字段

ALTER TABLE review_tasks ADD COLUMN IF NOT EXISTS pr_description TEXT;
ALTER TABLE review_tasks ADD COLUMN IF NOT EXISTS description_posted BOOLEAN NOT NULL DEFAULT FALSE;
```

- [ ] **Step 2: 在 ORM 模型中添加对应字段**

在 `apps/backend/src/code_review/models/db.py` 的 `ReviewTask` 类中（约行 84-85，`summary` 字段后）添加：

```python
    pr_description = Column(Text, nullable=True, comment="生成的 PR 摘要内容")
    description_posted = Column(Boolean, nullable=False, default=False, comment="是否已发布 PR 摘要到平台")
```

- [ ] **Step 3: 运行迁移并验证**

```bash
psql -U postgres -d code_review -f apps/backend/migrations/add_pr_description.sql
cd apps/backend && python -c "from code_review.models.db import ReviewTask; print('OK')"
```

- [ ] **Step 4: 提交**

```bash
git add apps/backend/migrations/add_pr_description.sql apps/backend/src/code_review/models/db.py
git commit -m "feat: review_tasks 表新增 pr_description 和 description_posted 字段"
```

---

### Task 2: 系统配置项 — PR 摘要开关和模式

**Files:**
- Modify: `apps/backend/migrations/add_pr_description.sql`（追加种子数据）

- [ ] **Step 1: 在迁移脚本中追加系统配置种子数据**

在 `add_pr_description.sql` 末尾追加：

```sql
-- PR 摘要系统配置
INSERT INTO system_settings (key, value, value_type, input_type, category, label, description, unit, default_value, options, sort_order)
VALUES
    ('pr_description_enabled', 'true', 'bool', 'switch', 'review', 'PR 摘要自动发布', '评审完成后是否自动生成并发布 PR 摘要评论', '', 'true', NULL, 40),
    ('pr_description_mode', 'full', 'string', 'select', 'review', 'PR 摘要模式', '摘要内容模式：summary_only 仅摘要 / full 摘要+统计+文件列表', '', 'full', '["summary_only", "full"]', 41)
ON CONFLICT (key) DO NOTHING;
```

- [ ] **Step 2: 执行迁移验证**

```bash
psql -U postgres -d code_review -f apps/backend/migrations/add_pr_description.sql
cd apps/backend && python -c "
from code_review.services.system_settings_service import SystemSettingsService
print('配置种子验证通过')
"
```

- [ ] **Step 3: 提交**

```bash
git add apps/backend/migrations/add_pr_description.sql
git commit -m "feat: 新增 pr_description_enabled 和 pr_description_mode 系统配置"
```

---

### Task 3: PR 摘要构建方法

**Files:**
- Modify: `apps/backend/src/code_review/services/review_orchestrator.py`

- [ ] **Step 1: 在 ReviewOrchestrator 类中添加 `_build_pr_description` 方法**

在 `review_orchestrator.py` 的 `_combine_diffs` 方法附近（约行 637 前后）添加新方法：

```python
    def _build_pr_description(
        self,
        task: ReviewTask,
        comments: list,
        changes: list,
        mode: str = "full",
    ) -> str:
        """用评审结果组装 PR 摘要（不调用 LLM）。"""
        from collections import Counter

        body = "## AI 评审摘要\n\n"
        body += f"**{task.summary}**\n\n"

        if mode == "full":
            severity_counts = Counter(
                c.severity.value if hasattr(c.severity, 'value') else c.severity
                for c in comments
            )
            body += "| 级别 | 数量 |\n|------|------|\n"
            for sev in ("critical", "warning", "suggestion", "info"):
                count = severity_counts.get(sev, 0)
                if count > 0:
                    body += f"| {sev} | {count} |\n"

            file_list = sorted({
                c.file_path for c in comments if hasattr(c, 'file_path') and c.file_path
            })
            if file_list:
                body += "\n**涉及文件：**\n"
                for f in file_list[:10]:
                    body += f"- `{f}`\n"

        return body
```

- [ ] **Step 2: 验证方法可调用**

```bash
cd apps/backend && python -c "
from code_review.services.review_orchestrator import ReviewOrchestrator
print(hasattr(ReviewOrchestrator, '_build_pr_description'))
"
```

- [ ] **Step 3: 提交**

```bash
git add apps/backend/src/code_review/services/review_orchestrator.py
git commit -m "feat: 添加 _build_pr_description 方法组装 PR 摘要"
```

---

### Task 4: 编排器集成 — 评审完成后发布 PR 摘要

**Files:**
- Modify: `apps/backend/src/code_review/services/review_orchestrator.py:472-520`

- [ ] **Step 1: 在评论发布后、保存评论前插入摘要发布逻辑**

在 `execute_review` 方法中，将以下代码插入到 `publish_comments_batch` 调用之后（约行 480 之后）、`保存评审意见到数据库` 注释之前（约行 482）：

```python
                # 生成并发布 PR 摘要
                settings_svc = SystemSettingsService(session)
                pr_desc_enabled = await settings_svc.get_bool("pr_description_enabled", True)
                if pr_desc_enabled and task.summary:
                    pr_desc_mode = await settings_svc.get_string("pr_description_mode", "full")
                    pr_description = self._build_pr_description(
                        task, result.comments, filtered_changes, mode=pr_desc_mode,
                    )
                    try:
                        from code_review.core.platform import PublishComment
                        await adapter.publish_comment(
                            project.platform_project_id,
                            task.mr_iid,
                            PublishComment(body=pr_description, position=None),
                        )
                        task.pr_description = pr_description
                        task.description_posted = True
                        logger.info("PR 摘要已发布: task=%s", task_id)
                    except Exception as e:
                        logger.warning("PR 摘要发布失败（不影响评审结果）: %s", e)
```

- [ ] **Step 2: 确认 import 已存在**

`SystemSettingsService` 已在行 387 导入（`from code_review.services.system_settings_service import SystemSettingsService`）。`PublishComment` 需要确认已导入，如果未导入则在文件顶部添加。

- [ ] **Step 3: 验证语法正确**

```bash
cd apps/backend && python -m py_compile src/code_review/services/review_orchestrator.py
```

- [ ] **Step 4: 提交**

```bash
git add apps/backend/src/code_review/services/review_orchestrator.py
git commit -m "feat: 评审完成后自动发布 PR 摘要到平台"
```

---

### Task 5: 前端 — 系统设置页 PR 摘要配置

**Files:**
- 修改: `apps/frontend/src/views/system/` 相关组件
- 修改: `apps/frontend/src/api/systemSettings.js`（如需）

- [ ] **Step 1: 确认系统设置页已自动支持新配置项**

系统设置页使用通用的 key-value 渲染，新增的 `pr_description_enabled`（switch 类型）和 `pr_description_mode`（select 类型）应自动出现在"review"分类下。验证前端是否按 category 分组渲染。

- [ ] **Step 2: 手动测试前端显示**

启动前端 `npm run dev`，进入系统设置页，确认 review 分类下出现 PR 摘要开关和模式选择。

- [ ] **Step 3: 提交（如有前端变更）**

```bash
git add apps/frontend/src/
git commit -m "feat: 前端系统设置页支持 PR 摘要配置"
```

---

## Feature B: P1-3 通知渠道增强（企微/Slack）

### 文件结构

| 操作 | 文件路径 | 职责 |
|------|---------|------|
| Create | `apps/backend/src/code_review/infrastructure/notification_wecom.py` | 企业微信渠道实现 |
| Create | `apps/backend/src/code_review/infrastructure/notification_slack.py` | Slack 渠道实现 |
| Modify | `apps/backend/src/code_review/infrastructure/notification_manager.py:16-20` | 注册新渠道到 CHANNEL_REGISTRY |
| Create | 迁移脚本（通知模板种子数据） | 企微和 Slack 默认模板 |

### Task 6: 通知模板种子数据 — 企微和 Slack

**Files:**
- Create: `apps/backend/migrations/add_notification_wecom_slack.sql`

- [ ] **Step 1: 创建迁移脚本**

```sql
-- apps/backend/migrations/add_notification_wecom_slack.sql
-- P1-3: 新增企业微信和 Slack 默认通知模板

INSERT INTO notification_templates (id, name, channel, description, title_template, body_template, enabled, is_default)
VALUES (
    gen_random_uuid(), 'default_wecom', 'wecom', '企业微信默认模板',
    '{{project_name}} 评审通知',
    '> **{{project_name}}** 评审完成\n> MR: [{{mr_title}}]({{mr_url}})\n> 作者: {{mr_author}}\n> Critical: {{critical_count}} | Warning: {{warning_count}}',
    true, true
);

INSERT INTO notification_templates (id, name, channel, description, title_template, body_template, enabled, is_default)
VALUES (
    gen_random_uuid(), 'default_slack', 'slack', 'Slack 默认模板',
    '{{project_name}} Review Notification',
    '*{{project_name}}* review completed\n• MR: <{{mr_url}}|{{mr_title}}>\n• Author: {{mr_author}}\n• Critical: {{critical_count}} | Warning: {{warning_count}}',
    true, true
);
```

- [ ] **Step 2: 执行迁移验证**

```bash
psql -U postgres -d code_review -f apps/backend/migrations/add_notification_wecom_slack.sql
```

- [ ] **Step 3: 提交**

```bash
git add apps/backend/migrations/add_notification_wecom_slack.sql
git commit -m "feat: 新增企业微信和 Slack 默认通知模板种子数据"
```

---

### Task 7: 企业微信通知渠道实现

**Files:**
- Create: `apps/backend/src/code_review/infrastructure/notification_wecom.py`

- [ ] **Step 1: 实现企业微信渠道**

参照 `notification_dingtalk.py` 和 `notification_feishu.py` 的模式，创建 `notification_wecom.py`：

```python
"""企业微信机器人通知渠道。"""

import logging
import time

import httpx

from code_review.core.notification import NotificationChannel, NotificationPayload, NotificationResult

logger = logging.getLogger(__name__)

_MAX_CONTENT_LENGTH = 4096


def _render_markdown(payload: NotificationPayload) -> str:
    """渲染企业微信 Markdown 消息内容。"""
    parts = [f"### {payload.project_name} 评审通知\n"]

    parts.append(f"> **MR:** [{payload.mr_title}]({payload.mr_url})")
    parts.append(f"> **作者:** {payload.mr_author}")

    if payload.critical_count > 0 or payload.warning_count > 0:
        stats = []
        if payload.critical_count > 0:
            stats.append(f"Critical: {payload.critical_count}")
        if payload.warning_count > 0:
            stats.append(f"Warning: {payload.warning_count}")
        if payload.suggestion_count > 0:
            stats.append(f"Suggestion: {payload.suggestion_count}")
        parts.append("> " + " | ".join(stats))

    if payload.summary:
        parts.append(f"\n> {payload.summary[:200]}")

    content = "\n".join(parts)
    if len(content.encode("utf-8")) > _MAX_CONTENT_LENGTH:
        content = content[:_MAX_CONTENT_LENGTH - 3] + "..."
    return content


class WeComChannel(NotificationChannel):
    """企业微信 Webhook 通知渠道。"""

    def __init__(self, config, timeout: int = 30):
        self._enabled = getattr(config, "enabled", False)
        self._webhook_url = getattr(config, "webhook_url", "")
        self._timeout = None if timeout == -1 else timeout

    @property
    def name(self) -> str:
        return "wecom"

    @property
    def enabled(self) -> bool:
        return self._enabled and bool(self._webhook_url)

    async def send(self, payload: NotificationPayload) -> NotificationResult:
        req_headers = {"Content-Type": "application/json"}

        if not self.enabled:
            return NotificationResult(
                success=False,
                provider="wecom",
                url=self._webhook_url,
                request_headers=req_headers,
                error_message="渠道未启用或 Webhook URL 未配置",
            )

        t0 = time.perf_counter()
        body: dict = {}
        try:
            content = payload.rendered_body if payload.rendered_body else _render_markdown(payload)
            body = {
                "msgtype": "markdown",
                "markdown": {"content": content},
            }
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(self._webhook_url, json=body, headers=req_headers)

            duration_ms = int((time.perf_counter() - t0) * 1000)
            resp_body: dict = {}
            try:
                resp_body = resp.json()
            except Exception:
                pass

            if resp.status_code == 200 and resp_body.get("errcode") == 0:
                logger.info("WeCom notification sent for MR: %s", payload.mr_title)
                return NotificationResult(
                    success=True,
                    provider="wecom",
                    url=self._webhook_url,
                    request_headers=req_headers,
                    request_body=body,
                    response_status=resp.status_code,
                    response_body=resp_body,
                    duration_ms=duration_ms,
                )

            error_msg = resp_body.get("errmsg", f"HTTP {resp.status_code}")
            logger.error("WeCom notification failed: %s", error_msg)
            return NotificationResult(
                success=False,
                provider="wecom",
                url=self._webhook_url,
                request_headers=req_headers,
                request_body=body,
                response_status=resp.status_code,
                response_body=resp_body,
                error_message=error_msg,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            logger.error("WeCom notification error: %s", e)
            return NotificationResult(
                success=False,
                provider="wecom",
                url=self._webhook_url,
                request_headers=req_headers,
                request_body=body,
                error_message=str(e),
                duration_ms=duration_ms,
            )

    async def health_check(self) -> bool:
        if not self.enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(self._webhook_url)
                return resp.status_code == 200
        except Exception:
            return False
```

- [ ] **Step 2: 验证语法**

```bash
cd apps/backend && python -m py_compile src/code_review/infrastructure/notification_wecom.py
```

- [ ] **Step 3: 提交**

```bash
git add apps/backend/src/code_review/infrastructure/notification_wecom.py
git commit -m "feat: 实现企业微信 Webhook 通知渠道"
```

---

### Task 8: Slack 通知渠道实现

**Files:**
- Create: `apps/backend/src/code_review/infrastructure/notification_slack.py`

- [ ] **Step 1: 实现 Slack 渠道**

```python
"""Slack Webhook 通知渠道。"""

import logging
import time

import httpx

from code_review.core.notification import NotificationChannel, NotificationPayload, NotificationResult

logger = logging.getLogger(__name__)

_MAX_BLOCKS = 50


def _build_blocks(payload: NotificationPayload) -> list[dict]:
    """构建 Slack Block Kit 消息。"""
    blocks: list[dict] = []

    # 标题
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": f"{payload.project_name} 评审通知"},
    })

    # 摘要
    if payload.summary:
        summary_text = payload.summary[:500]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*摘要:*\n{summary_text}"},
        })

    # MR 信息
    fields = [
        {"type": "mrkdwn", "text": f"*MR:*\n<{payload.mr_url}|{payload.mr_title}>"},
        {"type": "mrkdwn", "text": f"*作者:*\n{payload.mr_author}"},
    ]
    blocks.append({"type": "section", "fields": fields})

    # 统计信息
    stats_parts = []
    if payload.critical_count > 0:
        stats_parts.append(f"Critical: {payload.critical_count}")
    if payload.warning_count > 0:
        stats_parts.append(f"Warning: {payload.warning_count}")
    if payload.suggestion_count > 0:
        stats_parts.append(f"Suggestion: {payload.suggestion_count}")
    if payload.info_count > 0:
        stats_parts.append(f"Info: {payload.info_count}")

    if stats_parts:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": " | ".join(stats_parts)},
        })

    # 查看 MR 按钮
    blocks.append({
        "type": "actions",
        "elements": [{
            "type": "button",
            "text": {"type": "plain_text", "text": "查看 MR"},
            "url": payload.mr_url,
        }],
    })

    return blocks[:_MAX_BLOCKS]


class SlackChannel(NotificationChannel):
    """Slack Webhook 通知渠道。"""

    def __init__(self, config, timeout: int = 30):
        self._enabled = getattr(config, "enabled", False)
        self._webhook_url = getattr(config, "webhook_url", "")
        self._timeout = None if timeout == -1 else timeout

    @property
    def name(self) -> str:
        return "slack"

    @property
    def enabled(self) -> bool:
        return self._enabled and bool(self._webhook_url)

    async def send(self, payload: NotificationPayload) -> NotificationResult:
        req_headers = {"Content-Type": "application/json"}

        if not self.enabled:
            return NotificationResult(
                success=False,
                provider="slack",
                url=self._webhook_url,
                request_headers=req_headers,
                error_message="渠道未启用或 Webhook URL 未配置",
            )

        t0 = time.perf_counter()
        body: dict = {}
        try:
            if payload.rendered_body:
                body = {"text": payload.rendered_body}
            else:
                body = {
                    "blocks": _build_blocks(payload),
                    "text": f"{payload.project_name} review completed: {payload.mr_title}",
                }

            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(self._webhook_url, json=body, headers=req_headers)

            duration_ms = int((time.perf_counter() - t0) * 1000)
            resp_body: dict = {}
            try:
                resp_body = resp.json()
            except Exception:
                pass

            if resp.status_code == 200 and resp_body.get("ok", True):
                logger.info("Slack notification sent for MR: %s", payload.mr_title)
                return NotificationResult(
                    success=True,
                    provider="slack",
                    url=self._webhook_url,
                    request_headers=req_headers,
                    request_body=body,
                    response_status=resp.status_code,
                    response_body=resp_body,
                    duration_ms=duration_ms,
                )

            error_msg = resp_body.get("error", f"HTTP {resp.status_code}")
            logger.error("Slack notification failed: %s", error_msg)
            return NotificationResult(
                success=False,
                provider="slack",
                url=self._webhook_url,
                request_headers=req_headers,
                request_body=body,
                response_status=resp.status_code,
                response_body=resp_body,
                error_message=error_msg,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            logger.error("Slack notification error: %s", e)
            return NotificationResult(
                success=False,
                provider="slack",
                url=self._webhook_url,
                request_headers=req_headers,
                request_body=body,
                error_message=str(e),
                duration_ms=duration_ms,
            )

    async def health_check(self) -> bool:
        if not self.enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.post(
                    self._webhook_url,
                    json={"text": "health check"},
                    headers={"Content-Type": "application/json"},
                )
                return resp.status_code == 200
        except Exception:
            return False
```

- [ ] **Step 2: 验证语法**

```bash
cd apps/backend && python -m py_compile src/code_review/infrastructure/notification_slack.py
```

- [ ] **Step 3: 提交**

```bash
git add apps/backend/src/code_review/infrastructure/notification_slack.py
git commit -m "feat: 实现 Slack Webhook 通知渠道"
```

---

### Task 9: 注册新渠道到 CHANNEL_REGISTRY

**Files:**
- Modify: `apps/backend/src/code_review/infrastructure/notification_manager.py`

- [ ] **Step 1: 在导入和注册表中添加新渠道**

在 `notification_manager.py` 顶部导入区（行 8-10）添加：

```python
from code_review.infrastructure.notification_wecom import WeComChannel
from code_review.infrastructure.notification_slack import SlackChannel
```

在 `CHANNEL_REGISTRY` 字典（行 16-20）中添加：

```python
CHANNEL_REGISTRY: dict[str, type[NotificationChannel]] = {
    "feishu": FeishuChannel,
    "dingtalk": DingTalkChannel,
    "email": EmailChannel,
    "wecom": WeComChannel,
    "slack": SlackChannel,
}
```

- [ ] **Step 2: 验证语法**

```bash
cd apps/backend && python -m py_compile src/code_review/infrastructure/notification_manager.py
```

- [ ] **Step 3: 提交**

```bash
git add apps/backend/src/code_review/infrastructure/notification_manager.py
git commit -m "feat: 注册企业微信和 Slack 通知渠道到 CHANNEL_REGISTRY"
```

---

### Task 10: 前端 — 通知配置页支持新渠道

**Files:**
- Modify: `apps/frontend/src/views/notification/` 相关组件

- [ ] **Step 1: 确认通知配置表单支持动态渠道**

通知配置页面的渠道选择器使用 `notification_configs.channel` 字段，新增的 `wecom` 和 `slack` 值会自动出现（只要后端 API 返回）。检查前端是否有硬编码的渠道列表，如有则添加 `wecom` 和 `slack` 选项。

- [ ] **Step 2: 确认通知模板页支持新渠道筛选**

通知模板管理页的渠道筛选下拉框需包含 `wecom` 和 `slack`。检查 `apps/frontend/src/views/notification/` 目录下的模板管理组件。

- [ ] **Step 3: 构建验证**

```bash
cd apps/frontend && npm run build
```

- [ ] **Step 4: 提交（如有变更）**

```bash
git add apps/frontend/src/
git commit -m "feat: 前端通知配置支持企业微信和 Slack 渠道"
```

---

## 验证清单

### PR 摘要验证

- [ ] 触发评审后，检查 `review_tasks` 表中 `pr_description` 有值、`description_posted` 为 true
- [ ] PR/MR 上出现通用评论（`position=None`），包含摘要+统计+文件列表
- [ ] 关闭 `pr_description_enabled` 后不发布摘要
- [ ] `pr_description_mode=summary_only` 时只包含摘要文本

### 通知增强验证

- [ ] 在通知配置页新增企业微信配置，填入 Webhook URL，启用
- [ ] 触发评审后企业微信收到 Markdown 格式通知
- [ ] 新增 Slack 配置，触发评审后 Slack 收到 Block Kit 格式通知
- [ ] 通知模板管理页可筛选 wecom 和 slack 渠道
- [ ] 发送失败时 `api_call_logs` 表有记录
