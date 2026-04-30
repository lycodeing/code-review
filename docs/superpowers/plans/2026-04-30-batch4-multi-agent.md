# Batch 4: 多智能体评审架构 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将单次 LLM 调用拆分为多个专项 Agent（安全、性能、风格），并行评审后汇总去重。

**Architecture:** 新增 `AgentProfile` 数据类描述 Agent 配置，`MultiAgentReviewer` 调度器负责并行调用 LLM 并合并结果。编排器根据系统配置选择单/多 Agent 模式。默认关闭，手动开启。

**Tech Stack:** Python 3.11+, asyncio.gather, LangChain, SQLAlchemy async

---

## Feature G: P1-4 多智能体评审架构

### 文件结构

| 操作 | 文件路径 | 职责 |
|------|---------|------|
| Create | `apps/backend/migrations/add_agent_mode.sql` | 数据库迁移 |
| Modify | `apps/backend/src/code_review/models/db.py` | ReviewTask 新增 agent_mode 字段 |
| Create | `apps/backend/src/code_review/core/agent_profile.py` | Agent 配置模型 |
| Create | `apps/backend/src/code_review/services/multi_agent_reviewer.py` | 多 Agent 调度器 |
| Modify | `apps/backend/src/code_review/services/review_orchestrator.py` | 集成多 Agent 模式 |

### Task 1: 数据库迁移

**Files:**
- Create: `apps/backend/migrations/add_agent_mode.sql`

- [ ] **Step 1: 创建迁移脚本**

```sql
-- apps/backend/migrations/add_agent_mode.sql
-- P1-4: 多智能体评审 — review_tasks 新增 agent_mode 字段 + 系统配置

ALTER TABLE review_tasks ADD COLUMN IF NOT EXISTS agent_mode VARCHAR(16) NOT NULL DEFAULT 'single';

-- 系统配置
INSERT INTO system_settings (key, value, value_type, input_type, category, label, description, unit, default_value, options, sort_order)
VALUES
    ('agent_mode', 'single', 'string', 'select', 'review', '评审模式', 'single 单 Agent（现有模式）/ multi 多 Agent 并行', '', 'single', '["single", "multi"]', 60),
    ('agent_profiles', '[{"name":"security","focus":"安全漏洞、敏感信息泄露、注入风险","severity":"critical"},{"name":"performance","focus":"性能瓶颈、资源泄漏、N+1 查询","severity":"warning"},{"name":"quality","focus":"代码风格、可维护性、命名规范、重复代码","severity":"suggestion"}]', 'string', 'text', 'review', 'Agent 配置', '多 Agent 模式下的 Agent Profile JSON 数组', '', '[]', NULL, 61)
ON CONFLICT (key) DO NOTHING;
```

- [ ] **Step 2: ORM 模型同步**

在 `models/db.py` 的 `ReviewTask` 类（约行 96 `is_latest` 字段后）添加：

```python
    agent_mode = Column(String(16), nullable=False, default="single", comment="评审模式: single/multi")
```

- [ ] **Step 3: 执行迁移**

```bash
psql -U postgres -d code_review -f apps/backend/migrations/add_agent_mode.sql
```

- [ ] **Step 4: 提交**

```bash
git add apps/backend/migrations/add_agent_mode.sql apps/backend/src/code_review/models/db.py
git commit -m "feat: review_tasks 新增 agent_mode 字段 + 系统配置"
```

---

### Task 2: Agent 配置模型

**Files:**
- Create: `apps/backend/src/code_review/core/agent_profile.py`

- [ ] **Step 1: 实现 AgentProfile 数据类**

```python
"""Agent 配置模型 — 描述单个评审 Agent 的关注点和参数。"""

from dataclasses import dataclass


@dataclass
class AgentProfile:
    """单个评审 Agent 的配置。"""

    name: str
    focus: str
    severity: str = "warning"
    system_prompt: str = ""

    def build_prompt(self, base_template: str) -> str:
        """在基础模板上追加 Agent 专属指令。"""
        additions = [
            f"\n\n**重点关注：** {self.focus}",
            f"**报告级别：** {self.severity}",
        ]
        if self.system_prompt:
            additions.insert(0, f"\n**角色：** {self.system_prompt}")
        return base_template + "\n".join(additions)
```

- [ ] **Step 2: 提交**

```bash
git add apps/backend/src/code_review/core/agent_profile.py
git commit -m "feat: 实现 AgentProfile 配置模型"
```

---

### Task 3: 多 Agent 调度器

**Files:**
- Create: `apps/backend/src/code_review/services/multi_agent_reviewer.py`

- [ ] **Step 1: 实现 MultiAgentReviewer**

```python
"""多 Agent 并行评审调度器。"""

import asyncio
import logging
from difflib import SequenceMatcher
from uuid import UUID

from code_review.core.agent_profile import AgentProfile
from code_review.core.platform import FileChange
from code_review.infrastructure.langchain_reviewer import LangChainReviewer
from code_review.models.config import LLMConfig

logger = logging.getLogger(__name__)

_DEDUP_SIMILARITY = 0.8


class ReviewResult:
    """评审结果容器。"""
    def __init__(self, model: str, comments: list, summary: str,
                 total_tokens: int, elapsed_seconds: float):
        self.model = model
        self.comments = comments
        self.summary = summary
        self.total_tokens = total_tokens
        self.elapsed_seconds = elapsed_seconds


class MultiAgentReviewer:
    """多 Agent 并行评审调度器。"""

    def __init__(self, profiles: list[AgentProfile]):
        self._profiles = profiles

    async def review(
        self,
        diff: str,
        files: list[FileChange],
        base_template: str,
        llm_candidates: list[tuple[str, LLMConfig]],
        task_id: UUID | None = None,
        session_factory=None,
        project_id: UUID | None = None,
    ) -> ReviewResult:
        """并行执行多 Agent 评审，返回汇总结果。"""
        tasks = []
        for profile in self._profiles:
            agent_prompt = profile.build_prompt(base_template)
            tasks.append(
                self._single_agent_review(
                    profile, diff, files, agent_prompt, llm_candidates,
                    task_id, session_factory, project_id,
                )
            )

        agent_results = await asyncio.gather(*tasks, return_exceptions=True)

        successful: list[ReviewResult] = []
        for i, r in enumerate(agent_results):
            if isinstance(r, Exception):
                logger.warning("Agent %s 失败: %s", self._profiles[i].name, r)
            elif r is not None:
                successful.append(r)

        if not successful:
            raise RuntimeError("所有 Agent 均失败")

        return self._merge_agent_results(successful)

    async def _single_agent_review(
        self,
        profile: AgentProfile,
        diff: str,
        files: list[FileChange],
        prompt: str,
        llm_candidates: list[tuple[str, LLMConfig]],
        task_id: UUID | None = None,
        session_factory=None,
        project_id: UUID | None = None,
    ) -> ReviewResult:
        """单个 Agent 调用（复用 LangChainReviewer）。"""
        for config_name, llm_settings in llm_candidates:
            try:
                reviewer = LangChainReviewer(llm_settings)
                result = await reviewer.review(
                    diff=diff,
                    files=files,
                    prompt_template=prompt,
                    task_id=task_id,
                    session_factory=session_factory,
                    project_id=project_id,
                )
                logger.info("Agent %s 使用 %s 成功", profile.name, config_name)
                return result
            except Exception as e:
                logger.warning("Agent %s 配置 %s 失败: %s", profile.name, config_name, e)
                continue

        raise RuntimeError(f"Agent {profile.name} 所有 LLM 配置均失败")

    def _merge_agent_results(self, results: list[ReviewResult]) -> ReviewResult:
        """汇总多个 Agent 结果：去重 + 合并摘要。"""
        all_comments = []
        for r in results:
            all_comments.extend(r.comments)

        deduped = self._deduplicate(all_comments)
        summaries = [r.summary for r in results if r.summary]

        return ReviewResult(
            model="multi-agent",
            comments=deduped,
            summary="\n\n".join(summaries),
            total_tokens=sum(r.total_tokens for r in results),
            elapsed_seconds=max(r.elapsed_seconds for r in results),
        )

    @staticmethod
    def _deduplicate(comments: list) -> list:
        """去重策略：同文件同行号只保留严重程度最高的，文本相似度 > 0.8 视为重复。"""
        severity_rank = {"critical": 4, "warning": 3, "suggestion": 2, "info": 1}
        seen: dict[tuple, int] = {}
        result: list = []

        for c in comments:
            key = (c.file_path, c.line_start)
            sev_val = severity_rank.get(
                c.severity.value if hasattr(c.severity, "value") else c.severity, 0
            )

            if key in seen:
                existing_idx = seen[key]
                existing_sev = severity_rank.get(
                    result[existing_idx].severity.value
                    if hasattr(result[existing_idx].severity, "value")
                    else result[existing_idx].severity, 0
                )
                if sev_val > existing_sev:
                    result[existing_idx] = c
                continue

            # 文本相似度检查
            is_dup = False
            for existing in result:
                if (existing.file_path == c.file_path and
                    existing.line_start == c.line_start):
                    msg_existing = existing.message or ""
                    msg_new = c.message or ""
                    if SequenceMatcher(None, msg_existing, msg_new).ratio() > _DEDUP_SIMILARITY:
                        is_dup = True
                        break
            if not is_dup:
                seen[key] = len(result)
                result.append(c)

        return result
```

- [ ] **Step 2: 验证语法**

```bash
cd apps/backend && python -m py_compile src/code_review/services/multi_agent_reviewer.py
```

- [ ] **Step 3: 提交**

```bash
git add apps/backend/src/code_review/services/multi_agent_reviewer.py
git commit -m "feat: 实现多 Agent 并行评审调度器 MultiAgentReviewer"
```

---

### Task 4: 编排器集成多 Agent 模式

**Files:**
- Modify: `apps/backend/src/code_review/services/review_orchestrator.py:415-448`

- [ ] **Step 1: 在 LLM 调用循环前添加模式选择**

在 `execute_review` 方法中，将现有行 415-448 的 LLM 调用循环替换为模式感知逻辑：

```python
                # 读取评审模式
                agent_mode = await settings_svc.get_string("agent_mode", "single")

                if agent_mode == "multi":
                    # 多 Agent 并行模式
                    import json
                    from code_review.core.agent_profile import AgentProfile
                    from code_review.services.multi_agent_reviewer import MultiAgentReviewer

                    profiles_json = await settings_svc.get_string(
                        "agent_profiles",
                        '[{"name":"security","focus":"安全漏洞、敏感信息泄露、注入风险","severity":"critical"},'
                        '{"name":"performance","focus":"性能瓶颈、资源泄漏、N+1 查询","severity":"warning"},'
                        '{"name":"quality","focus":"代码风格、可维护性、命名规范、重复代码","severity":"suggestion"}]',
                    )
                    try:
                        profiles_data = json.loads(profiles_json)
                        profiles = [AgentProfile(**p) for p in profiles_data]
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning("Agent profiles JSON 解析失败，降级到单 Agent: %s", e)
                        agent_mode = "single"
                        profiles = []

                    if profiles:
                        reviewer = MultiAgentReviewer(profiles)
                        result = await reviewer.review(
                            diff=combined_diff,
                            files=filtered_changes,
                            base_template=prompt,
                            llm_candidates=llm_candidates,
                            task_id=task.id,
                            session_factory=self._session_factory,
                            project_id=task.project_id,
                        )
                        task.model_name = "multi-agent"
                        task.agent_mode = "multi"
                        logger.info("多 Agent 评审完成: %d 个 Agent, %d 条评论",
                                    len(profiles), len(result.comments))

                if agent_mode == "single" or result is None:
                    # 现有单 Agent 逻辑（原行 420-448 的 for 循环）
                    for config_name, llm_settings in llm_candidates:
                        try:
                            logger.info("尝试 LLM 配置: %s, model=%s", config_name, llm_settings.model)
                            reviewer = LangChainReviewer(llm_settings)
                            result = await reviewer.review(
                                diff=combined_diff,
                                files=filtered_changes,
                                prompt_template=prompt,
                                task_id=task.id,
                                session_factory=self._session_factory,
                                related_context=related_context if related_context else None,
                                project_id=task.project_id,
                            )
                            task.model_name = result.model
                            task.agent_mode = "single"
                            logger.info("LLM 配置 %s 评审成功, model=%s", config_name, result.model)
                            break
                        except Exception as e:
                            tried_configs.append(config_name)
                            last_error = e
                            logger.warning(
                                "LLM 配置 %s (model=%s) 调用失败: %s",
                                config_name, llm_settings.model, e,
                            )
                            if len(llm_candidates) > 1:
                                logger.info("尝试故障转移到下一个 LLM 配置...")
                            continue
```

注意：`result` 变量的初始化（行 416）需要提前到模式选择之前。

- [ ] **Step 2: 验证语法**

```bash
cd apps/backend && python -m py_compile src/code_review/services/review_orchestrator.py
```

- [ ] **Step 3: 提交**

```bash
git add apps/backend/src/code_review/services/review_orchestrator.py
git commit -m "feat: 编排器集成多 Agent 并行评审模式"
```

---

## 验证清单

### 多智能体验证

- [ ] 切换到多 Agent 模式，触发评审，检查 LLM 调用日志中有 3 次独立调用
- [ ] 相同问题的评论被去重（只保留严重程度最高的）
- [ ] 切回单 Agent 模式行为不变
- [ ] 某个 Agent LLM 调用失败不影响其他 Agent
- [ ] 多 Agent 模式下 `model_name` 记录为 `multi-agent`
- [ ] `review_tasks.agent_mode` 正确记录为 `single` 或 `multi`
- [ ] 系统设置页可切换评审模式
