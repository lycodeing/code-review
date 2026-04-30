# Batch 2: 全库上下文增强 + 增量学习 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现评审时自动加载相关文件上下文，以及将用户反馈沉淀为团队偏好规则注入后续评审 Prompt。

**Architecture:** 上下文增强通过新增 `ContextExtractor` 服务，复用已有 `PlatformAdapter.get_file_content()` 接口加载相关文件。增量学习通过新增 `LearningService` 和 `review_learnings` 表，在评论反馈时触发学习，在 LLM 调用时注入偏好。

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy async, LangChain, PostgreSQL

---

## Feature C: P0-3 全库上下文增强

### 文件结构

| 操作 | 文件路径 | 职责 |
|------|---------|------|
| Create | `apps/backend/src/code_review/services/context_extractor.py` | 上下文提取器 |
| Modify | `apps/backend/src/code_review/infrastructure/langchain_reviewer.py:95-113` | 扩展 review() 签名支持 related_context |
| Modify | `apps/backend/src/code_review/services/review_orchestrator.py:342-430` | diff 合并后插入上下文提取 |

### Task 1: 系统配置 — 上下文增强配置项

**Files:**
- Create: `apps/backend/migrations/add_context_enhancement.sql`

- [ ] **Step 1: 创建迁移脚本**

```sql
-- apps/backend/migrations/add_context_enhancement.sql
-- P0-3: 上下文增强系统配置

INSERT INTO system_settings (key, value, value_type, input_type, category, label, description, unit, default_value, options, sort_order)
VALUES
    ('context_enhancement_enabled', 'true', 'bool', 'switch', 'review', '上下文增强', '评审时是否自动加载相关文件作为附加上下文', '', 'true', NULL, 50),
    ('context_max_files', '5', 'int', 'number', 'review', '最大上下文文件数', '自动加载的相关文件最大数量', '个', '5', NULL, 51),
    ('context_max_file_size', '10000', 'int', 'number', 'review', '单文件最大字符数', '单个上下文文件最大加载字符数', '字符', '10000', NULL, 52)
ON CONFLICT (key) DO NOTHING;
```

- [ ] **Step 2: 执行迁移**

```bash
psql -U postgres -d code_review -f apps/backend/migrations/add_context_enhancement.sql
```

- [ ] **Step 3: 提交**

```bash
git add apps/backend/migrations/add_context_enhancement.sql
git commit -m "feat: 新增上下文增强系统配置项"
```

---

### Task 2: 上下文提取器服务

**Files:**
- Create: `apps/backend/src/code_review/services/context_extractor.py`

- [ ] **Step 1: 实现 ContextExtractor**

```python
"""上下文提取器 — 从 diff 中提取跨文件引用并加载相关文件内容。"""

import logging
import re

from code_review.core.platform import PlatformAdapter, FileChange

logger = logging.getLogger(__name__)

_IMPORT_PATTERNS: dict[str, list[str]] = {
    "python": [
        r"(?:from|import)\s+([a-zA-Z_][\w.]*)",
    ],
    "java": [
        r"import\s+(?:static\s+)?([\w.]+)",
    ],
    "go": [
        r'"([^"]+)"',
    ],
    "javascript": [
        r"(?:import\s+.*?from\s+|require\s*\(\s*)['\"]([^'\"]+)['\"]",
    ],
    "typescript": [
        r"(?:import\s+.*?from\s+|require\s*\(\s*)['\"]([^'\"]+)['\"]",
    ],
}

_EXTENSION_MAP: dict[str, str] = {
    "python": ".py",
    "java": ".java",
    "go": ".go",
    "javascript": ".js",
    "typescript": ".ts",
}


def _detect_language(file_path: str) -> str:
    ext = file_path.rsplit(".", 1)[-1] if "." in file_path else ""
    ext_map = {
        "py": "python", "java": "java", "go": "go",
        "js": "javascript", "jsx": "javascript",
        "ts": "typescript", "tsx": "typescript",
    }
    return ext_map.get(ext, "")


def _resolve_import_path(import_path: str, language: str) -> str:
    """将 import 路径转为文件系统路径。"""
    if language == "python":
        return import_path.replace(".", "/") + ".py"
    elif language == "java":
        return import_path.replace(".", "/") + ".java"
    elif language == "go":
        return import_path
    elif language in ("javascript", "typescript"):
        path = import_path.lstrip("@/").lstrip("./").lstrip("../")
        if not path.endswith((".js", ".jsx", ".ts", ".tsx")):
            path = path + "/index.ts" if language == "typescript" else path + "/index.js"
        return path
    return import_path


class ContextExtractor:
    """从 diff 中提取跨文件引用并加载相关文件内容。"""

    async def extract_context(
        self,
        adapter: PlatformAdapter,
        project_id: str,
        changes: list[FileChange],
        source_branch: str,
        max_files: int = 5,
        max_file_size: int = 10000,
    ) -> dict[str, str]:
        """提取并加载相关文件上下文。返回 {file_path: content} 映射。"""
        changed_paths = {c.path for c in changes}
        import_paths: dict[str, None] = {}

        for change in changes:
            language = _detect_language(change.path)
            if not language or language not in _IMPORT_PATTERNS:
                continue
            patterns = _IMPORT_PATTERNS[language]
            diff_text = change.diff or ""
            for pattern in patterns:
                for match in re.finditer(pattern, diff_text):
                    raw_import = match.group(1)
                    resolved = _resolve_import_path(raw_import, language)
                    if resolved and resolved not in changed_paths:
                        import_paths[resolved] = None

        if not import_paths:
            return {}

        result: dict[str, str] = {}
        for path in list(import_paths.keys())[:max_files]:
            try:
                content = await adapter.get_file_content(project_id, path, source_branch)
                if content:
                    if len(content) > max_file_size:
                        content = content[:max_file_size] + "\n... (已截断)"
                    result[path] = content
                    logger.debug("加载上下文文件: %s (%d 字符)", path, len(content))
            except Exception as e:
                logger.debug("跳过无法加载的文件 %s: %s", path, e)

        if result:
            logger.info("上下文增强: 加载了 %d 个相关文件", len(result))
        return result
```

- [ ] **Step 2: 验证语法**

```bash
cd apps/backend && python -m py_compile src/code_review/services/context_extractor.py
```

- [ ] **Step 3: 提交**

```bash
git add apps/backend/src/code_review/services/context_extractor.py
git commit -m "feat: 实现上下文提取器服务 ContextExtractor"
```

---

### Task 3: LangChainReviewer 扩展 — 支持 related_context

**Files:**
- Modify: `apps/backend/src/code_review/infrastructure/langchain_reviewer.py:95-113`

- [ ] **Step 1: 扩展 review() 方法签名**

在 `langchain_reviewer.py` 行 95-102，修改 `review` 方法签名，新增 `related_context` 参数：

```python
    async def review(
        self,
        diff: str,
        files: list[FileChange],
        prompt_template: str,
        task_id: UUID | None = None,
        session_factory=None,
        related_context: dict[str, str] | None = None,
    ) -> ReviewResult:
```

- [ ] **Step 2: 在 Prompt 组装阶段处理 related_context**

在行 112-113 的 Prompt 替换之后（行 113 后）添加：

```python
        # 注入相关文件上下文
        if related_context:
            ctx_parts = [
                f"### `{path}`\n```\n{content}\n```"
                for path, content in related_context.items()
            ]
            full_prompt = full_prompt.replace(
                "{{related_context}}", "\n\n".join(ctx_parts)
            )
        elif "{{related_context}}" in full_prompt:
            full_prompt = full_prompt.replace("{{related_context}}", "（无额外上下文）")
```

- [ ] **Step 3: 验证语法**

```bash
cd apps/backend && python -m py_compile src/code_review/infrastructure/langchain_reviewer.py
```

- [ ] **Step 4: 提交**

```bash
git add apps/backend/src/code_review/infrastructure/langchain_reviewer.py
git commit -m "feat: LangChainReviewer 支持 related_context 参数注入上下文"
```

---

### Task 4: 编排器集成 — diff 合并后插入上下文提取

**Files:**
- Modify: `apps/backend/src/code_review/services/review_orchestrator.py:342-430`

- [ ] **Step 1: 在 diff 合并后、规则引擎前插入上下文提取**

在 `execute_review` 方法中，行 343 `combined_diff = self._combine_diffs(filtered_changes)` 之后，行 345 `# 执行规则引擎` 之前，插入：

```python
                # 上下文增强：加载 diff 中引用的相关文件
                related_context: dict[str, str] = {}
                ctx_enabled = await settings_svc.get_bool("context_enhancement_enabled", True)
                if ctx_enabled:
                    from code_review.services.context_extractor import ContextExtractor
                    ctx_extractor = ContextExtractor()
                    max_ctx_files = await settings_svc.get_int("context_max_files", 5)
                    max_ctx_size = await settings_svc.get_int("context_max_file_size", 10000)
                    related_context = await ctx_extractor.extract_context(
                        adapter=adapter,
                        project_id=project.platform_project_id,
                        changes=filtered_changes,
                        source_branch=task.source_branch or "main",
                        max_files=max_ctx_files,
                        max_file_size=max_ctx_size,
                    )
```

注意：`settings_svc` 已在行 387-389 定义，但需要将它提前到行 342 之前。将行 387-389 的代码移到行 342 之前，并移除行 387-389 的重复定义。

- [ ] **Step 2: 在 LLM 调用处传递 related_context**

在行 424-430 的 `reviewer.review()` 调用中，新增 `related_context` 参数：

```python
                        result = await reviewer.review(
                            diff=combined_diff,
                            files=filtered_changes,
                            prompt_template=prompt,
                            task_id=task.id,
                            session_factory=self._session_factory,
                            related_context=related_context if related_context else None,
                        )
```

- [ ] **Step 3: 验证语法**

```bash
cd apps/backend && python -m py_compile src/code_review/services/review_orchestrator.py
```

- [ ] **Step 4: 提交**

```bash
git add apps/backend/src/code_review/services/review_orchestrator.py
git commit -m "feat: 编排器集成上下文增强，diff 合并后提取相关文件"
```

---

## Feature D: P0-1 增量学习 / 团队偏好记忆

### 文件结构

| 操作 | 文件路径 | 职责 |
|------|---------|------|
| Create | `apps/backend/migrations/add_review_learnings.sql` | 新建 review_learnings 表 |
| Modify | `apps/backend/src/code_review/models/db.py` | 新增 ReviewLearning ORM 模型 |
| Create | `apps/backend/src/code_review/services/learning_service.py` | 偏好学习服务 |
| Create | `apps/backend/src/code_review/api/learnings.py` | 偏好管理 API |
| Modify | `apps/backend/src/code_review/api/comments.py` | 反馈触发学习 |
| Modify | `apps/backend/src/code_review/infrastructure/langchain_reviewer.py` | Prompt 注入偏好 |
| Modify | `apps/backend/src/code_review/api/app.py` | 注册新路由 |
| Modify | `apps/backend/src/code_review/services/review_orchestrator.py` | 传递 project_id |

### Task 5: 数据库迁移 — review_learnings 表

**Files:**
- Create: `apps/backend/migrations/add_review_learnings.sql`

- [ ] **Step 1: 创建迁移脚本**

```sql
-- apps/backend/migrations/add_review_learnings.sql
-- P0-1: 增量学习 — 新增 review_learnings 表

CREATE TABLE IF NOT EXISTS review_learnings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_type VARCHAR(32) NOT NULL DEFAULT 'feedback',
    source_comment_id UUID REFERENCES review_comments(id) ON DELETE SET NULL,
    category VARCHAR(64) NOT NULL DEFAULT 'style',
    rule_text TEXT NOT NULL,
    context TEXT,
    feedback_sentiment VARCHAR(16),
    confidence INTEGER NOT NULL DEFAULT 1,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_learnings_project ON review_learnings(project_id);
CREATE INDEX IF NOT EXISTS idx_learnings_category ON review_learnings(project_id, category);
CREATE INDEX IF NOT EXISTS idx_learnings_enabled ON review_learnings(project_id, enabled);
```

- [ ] **Step 2: 执行迁移**

```bash
psql -U postgres -d code_review -f apps/backend/migrations/add_review_learnings.sql
```

- [ ] **Step 3: 提交**

```bash
git add apps/backend/migrations/add_review_learnings.sql
git commit -m "feat: 新增 review_learnings 表迁移脚本"
```

---

### Task 6: ORM 模型 — ReviewLearning

**Files:**
- Modify: `apps/backend/src/code_review/models/db.py`

- [ ] **Step 1: 在 db.py 中添加 ReviewLearning 模型**

在 `ReviewComment` 类之后（约行 169 之后）添加：

```python
class ReviewLearning(Base):
    """团队偏好学习记录表。"""
    __tablename__ = "review_learnings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    source_type = Column(String(32), nullable=False, default="feedback", comment="来源: feedback / manual")
    source_comment_id = Column(UUID(as_uuid=True), ForeignKey("review_comments.id", ondelete="SET NULL"), nullable=True)
    category = Column(String(64), nullable=False, default="style", comment="分类: style/pattern/naming/architecture/other")
    rule_text = Column(Text, nullable=False, comment="偏好规则描述")
    context = Column(Text, nullable=True, comment="原始评论上下文摘要")
    feedback_sentiment = Column(String(16), nullable=True, comment="positive / negative")
    confidence = Column(Integer, nullable=False, default=1, comment="置信度（相同反馈叠加）")
    enabled = Column(Boolean, nullable=False, default=True, comment="是否启用")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: now_cst())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: now_cst(), onupdate=lambda: now_cst())

    project = relationship("Project")
    source_comment = relationship("ReviewComment")

    __table_args__ = (
        Index("idx_learnings_project", "project_id"),
        Index("idx_learnings_category", "project_id", "category"),
        Index("idx_learnings_enabled", "project_id", "enabled"),
    )

    def __repr__(self) -> str:
        return f"<ReviewLearning {self.category}: {self.rule_text[:50]}>"
```

- [ ] **Step 2: 验证语法**

```bash
cd apps/backend && python -c "from code_review.models.db import ReviewLearning; print('OK')"
```

- [ ] **Step 3: 提交**

```bash
git add apps/backend/src/code_review/models/db.py
git commit -m "feat: 新增 ReviewLearning ORM 模型"
```

---

### Task 7: 偏好学习服务

**Files:**
- Create: `apps/backend/src/code_review/services/learning_service.py`

- [ ] **Step 1: 实现 LearningService**

```python
"""偏好学习服务 — 将用户反馈沉淀为项目级偏好规则。"""

import logging
from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from code_review.models.db import ReviewLearning, ReviewComment, ReviewTask

logger = logging.getLogger(__name__)

_SIMILARITY_THRESHOLD = 0.8
_MAX_PROMPT_LEARNINGS = 10


class LearningService:
    """团队偏好学习服务。"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def process_feedback(self, comment_id: UUID, feedback: str) -> ReviewLearning | None:
        """用户反馈触发学习。thumbs_up 强化规则，thumbs_down 生成反向偏好。"""
        comment = await self._session.get(ReviewComment, comment_id)
        if not comment:
            logger.warning("评论不存在: %s", comment_id)
            return None

        task = await self._session.get(ReviewTask, comment.task_id)
        if not task:
            return None

        sentiment = "positive" if feedback == "thumbs_up" else "negative"
        rule_text = self._generate_rule(comment, sentiment)
        if not rule_text:
            return None

        # 检查相似规则
        existing = await self._find_similar(task.project_id, rule_text)
        if existing:
            existing.confidence += 1
            existing.updated_at = func.now()
            await self._session.commit()
            await self._session.refresh(existing)
            logger.info("强化已有偏好规则 (confidence=%d): %s", existing.confidence, existing.rule_text[:50])
            return existing

        learning = ReviewLearning(
            project_id=task.project_id,
            source_type="feedback",
            source_comment_id=comment_id,
            category=self._classify_category(comment),
            rule_text=rule_text,
            context=comment.message[:200] if comment.message else None,
            feedback_sentiment=sentiment,
            confidence=1,
            enabled=True,
        )
        self._session.add(learning)
        await self._session.commit()
        await self._session.refresh(learning)
        logger.info("新增偏好规则: %s", rule_text[:50])
        return learning

    async def get_learnings_for_prompt(self, project_id: UUID, limit: int = _MAX_PROMPT_LEARNINGS) -> str:
        """查询项目启用的偏好规则，格式化为 Prompt 注入文本。"""
        stmt = (
            select(ReviewLearning)
            .where(
                ReviewLearning.project_id == project_id,
                ReviewLearning.enabled.is_(True),
            )
            .order_by(ReviewLearning.confidence.desc(), ReviewLearning.updated_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        learnings = list(result.scalars().all())

        if not learnings:
            return ""

        lines = []
        for l in learnings:
            priority = "高优先级" if l.confidence >= 3 else "参考"
            lines.append(f"- [{priority}] {l.rule_text}")
        return "\n".join(lines)

    async def add_manual_learning(
        self, project_id: UUID, rule_text: str, category: str = "style"
    ) -> ReviewLearning:
        """手动添加偏好规则。"""
        learning = ReviewLearning(
            project_id=project_id,
            source_type="manual",
            category=category,
            rule_text=rule_text,
            confidence=3,
            enabled=True,
        )
        self._session.add(learning)
        await self._session.commit()
        await self._session.refresh(learning)
        return learning

    async def merge_duplicate_learnings(self, project_id: UUID) -> int:
        """合并语义重复的偏好规则，叠加 confidence。返回合并数量。"""
        stmt = (
            select(ReviewLearning)
            .where(ReviewLearning.project_id == project_id, ReviewLearning.enabled.is_(True))
            .order_by(ReviewLearning.confidence.desc())
        )
        result = await self._session.execute(stmt)
        all_learnings = list(result.scalars().all())

        merged_count = 0
        to_remove: list[UUID] = []

        for i, learning in enumerate(all_learnings):
            if learning.id in to_remove:
                continue
            for other in all_learnings[i + 1:]:
                if other.id in to_remove:
                    continue
                if self._compute_similarity(learning.rule_text, other.rule_text) > _SIMILARITY_THRESHOLD:
                    learning.confidence += other.confidence
                    to_remove.append(other.id)
                    merged_count += 1

        if to_remove:
            await self._session.execute(
                update(ReviewLearning)
                .where(ReviewLearning.id.in_(to_remove))
                .values(enabled=False)
            )
            await self._session.commit()

        return merged_count

    async def _find_similar(self, project_id: UUID, rule_text: str) -> ReviewLearning | None:
        stmt = (
            select(ReviewLearning)
            .where(ReviewLearning.project_id == project_id, ReviewLearning.enabled.is_(True))
        )
        result = await self._session.execute(stmt)
        for existing in result.scalars().all():
            if self._compute_similarity(existing.rule_text, rule_text) > _SIMILARITY_THRESHOLD:
                return existing
        return None

    @staticmethod
    def _compute_similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    @staticmethod
    def _generate_rule(comment: ReviewComment, sentiment: str) -> str:
        if not comment.message:
            return ""
        msg = comment.message[:300]
        if sentiment == "positive":
            return f"认可此代码风格: {msg}"
        return f"应避免此类代码: {msg}"

    @staticmethod
    def _classify_category(comment: ReviewComment) -> str:
        msg = (comment.message or "").lower()
        if any(kw in msg for kw in ("命名", "naming", "variable", "函数名", "类名")):
            return "naming"
        if any(kw in msg for kw in ("架构", "architecture", "设计", "design", "模式", "pattern")):
            return "architecture"
        if any(kw in msg for kw in ("性能", "performance", "优化", "optimize", "内存", "memory")):
            return "pattern"
        return "style"
```

- [ ] **Step 2: 验证语法**

```bash
cd apps/backend && python -m py_compile src/code_review/services/learning_service.py
```

- [ ] **Step 3: 提交**

```bash
git add apps/backend/src/code_review/services/learning_service.py
git commit -m "feat: 实现偏好学习服务 LearningService"
```

---

### Task 8: 偏好管理 API

**Files:**
- Create: `apps/backend/src/code_review/api/learnings.py`

- [ ] **Step 1: 实现偏好管理 API 路由**

```python
"""团队偏好学习管理 API。"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from code_review.models.db import ReviewLearning
from code_review.services.learning_service import LearningService

router = APIRouter(prefix="/api/v1/learnings", tags=["learnings"])


class LearningCreate(BaseModel):
    rule_text: str
    category: str = "style"


class LearningUpdate(BaseModel):
    rule_text: str | None = None
    enabled: bool | None = None
    category: str | None = None


class LearningMergeResult(BaseModel):
    merged_count: int


@router.get("/{project_id}")
async def list_learnings(project_id: UUID, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        from sqlalchemy import select
        stmt = (
            select(ReviewLearning)
            .where(ReviewLearning.project_id == project_id)
            .order_by(ReviewLearning.confidence.desc(), ReviewLearning.created_at.desc())
        )
        result = await session.execute(stmt)
        learnings = list(result.scalars().all())
        return [
            {
                "id": str(l.id),
                "project_id": str(l.project_id),
                "source_type": l.source_type,
                "category": l.category,
                "rule_text": l.rule_text,
                "context": l.context,
                "feedback_sentiment": l.feedback_sentiment,
                "confidence": l.confidence,
                "enabled": l.enabled,
                "created_at": l.created_at.isoformat() if l.created_at else None,
                "updated_at": l.updated_at.isoformat() if l.updated_at else None,
            }
            for l in learnings
        ]


@router.post("/{project_id}")
async def create_learning(project_id: UUID, body: LearningCreate, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = LearningService(session)
        learning = await svc.add_manual_learning(project_id, body.rule_text, body.category)
        return {
            "id": str(learning.id),
            "rule_text": learning.rule_text,
            "category": learning.category,
            "confidence": learning.confidence,
        }


@router.put("/{learning_id}")
async def update_learning(learning_id: UUID, body: LearningUpdate, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        learning = await session.get(ReviewLearning, learning_id)
        if not learning:
            raise HTTPException(status_code=404, detail="偏好规则不存在")
        if body.rule_text is not None:
            learning.rule_text = body.rule_text
        if body.enabled is not None:
            learning.enabled = body.enabled
        if body.category is not None:
            learning.category = body.category
        await session.commit()
        await session.refresh(learning)
        return {
            "id": str(learning.id),
            "rule_text": learning.rule_text,
            "enabled": learning.enabled,
            "category": learning.category,
        }


@router.delete("/{learning_id}")
async def delete_learning(learning_id: UUID, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        learning = await session.get(ReviewLearning, learning_id)
        if not learning:
            raise HTTPException(status_code=404, detail="偏好规则不存在")
        await session.delete(learning)
        await session.commit()
        return {"detail": "已删除"}


@router.post("/{project_id}/merge")
async def merge_learnings(project_id: UUID, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        svc = LearningService(session)
        count = await svc.merge_duplicate_learnings(project_id)
        return LearningMergeResult(merged_count=count)
```

- [ ] **Step 2: 验证语法**

```bash
cd apps/backend && python -m py_compile src/code_review/api/learnings.py
```

- [ ] **Step 3: 提交**

```bash
git add apps/backend/src/code_review/api/learnings.py
git commit -m "feat: 实现偏好学习管理 API（CRUD + 合并）"
```

---

### Task 9: 注册学习路由 + 反馈触发学习

**Files:**
- Modify: `apps/backend/src/code_review/api/app.py`
- Modify: `apps/backend/src/code_review/api/comments.py`

- [ ] **Step 1: 在 app.py 注册 learnings 路由**

在 `app.py` 的导入区（约行 29 之后）添加：

```python
from code_review.api.learnings import router as learnings_router
```

在路由注册区（约行 162 `app.include_router(system_settings_router)` 之前）添加：

```python
    app.include_router(learnings_router)
```

- [ ] **Step 2: 修改 comments.py 反馈 API 触发学习**

修改 `apps/backend/src/code_review/api/comments.py` 中的 `update_comment_feedback` 函数，在保存反馈后触发学习：

```python
@router.patch("/{comment_id}/feedback")
async def update_comment_feedback(
    comment_id: str,
    body: FeedbackRequest,
    request: Request,
):
    if body.feedback not in (None, "thumbs_up", "thumbs_down"):
        raise HTTPException(
            status_code=422, detail="feedback 值必须为 thumbs_up、thumbs_down 或 null",
        )

    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        comment = await session.get(ReviewComment, UUID(comment_id))
        if not comment:
            raise HTTPException(status_code=404, detail="评论不存在")
        comment.feedback = body.feedback
        await session.commit()
        await session.refresh(comment)

        # 触发偏好学习
        if body.feedback in ("thumbs_up", "thumbs_down"):
            try:
                from code_review.services.learning_service import LearningService
                svc = LearningService(session)
                await svc.process_feedback(UUID(comment_id), body.feedback)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("偏好学习失败（不影响反馈保存）: %s", e)

        return {"id": str(comment.id), "feedback": comment.feedback}
```

- [ ] **Step 3: 验证语法**

```bash
cd apps/backend && python -m py_compile src/code_review/api/app.py src/code_review/api/comments.py
```

- [ ] **Step 4: 提交**

```bash
git add apps/backend/src/code_review/api/app.py apps/backend/src/code_review/api/comments.py
git commit -m "feat: 注册学习路由 + 评论反馈触发偏好学习"
```

---

### Task 10: Prompt 注入偏好 + 编排器传递 project_id

**Files:**
- Modify: `apps/backend/src/code_review/infrastructure/langchain_reviewer.py:95-113`
- Modify: `apps/backend/src/code_review/services/review_orchestrator.py`

- [ ] **Step 1: LangChainReviewer 扩展支持偏好注入**

在 `langchain_reviewer.py` 的 `review()` 方法签名中新增 `project_id` 和 `session_factory` 参数已存在（`task_id` 和 `session_factory` 已在签名中）。在 Prompt 组装阶段（related_context 处理之后）添加偏好注入：

```python
        # 注入团队偏好
        learning_context = ""
        if project_id and session_factory:
            try:
                async with session_factory() as l_session:
                    from code_review.services.learning_service import LearningService
                    l_svc = LearningService(l_session)
                    learning_context = await l_svc.get_learnings_for_prompt(project_id)
            except Exception as e:
                logger.warning("加载偏好规则失败: %s", e)
        if learning_context:
            full_prompt += f"\n\n## 团队偏好规则（请参考以下风格偏好）\n{learning_context}"
```

同时扩展 `review()` 方法签名，新增 `project_id` 参数：

```python
    async def review(
        self,
        diff: str,
        files: list[FileChange],
        prompt_template: str,
        task_id: UUID | None = None,
        session_factory=None,
        related_context: dict[str, str] | None = None,
        project_id: UUID | None = None,
    ) -> ReviewResult:
```

- [ ] **Step 2: 编排器传递 project_id**

在 `review_orchestrator.py` 的 `reviewer.review()` 调用处，新增 `project_id` 参数：

```python
                        result = await reviewer.review(
                            diff=combined_diff,
                            files=filtered_changes,
                            prompt_template=prompt,
                            task_id=task.id,
                            session_factory=self._session_factory,
                            related_context=related_context if related_context else None,
                            project_id=task.project_id,
                        )
```

- [ ] **Step 3: 验证语法**

```bash
cd apps/backend && python -m py_compile src/code_review/infrastructure/langchain_reviewer.py src/code_review/services/review_orchestrator.py
```

- [ ] **Step 4: 提交**

```bash
git add apps/backend/src/code_review/infrastructure/langchain_reviewer.py apps/backend/src/code_review/services/review_orchestrator.py
git commit -m "feat: Prompt 注入团队偏好规则，编排器传递 project_id"
```

---

## 验证清单

### 上下文增强验证

- [ ] Python PR 引用了 `utils.helper`，检查 LLM 日志中包含 `utils/helper.py` 内容
- [ ] 超过 `context_max_files` 时只加载前 N 个文件
- [ ] 文件内容超过 `context_max_file_size` 时正确截断
- [ ] 关闭 `context_enhancement_enabled` 后 `related_context` 为空
- [ ] 不存在的文件路径优雅跳过（不报错）

### 增量学习验证

- [ ] 对评论点赞后检查 `review_learnings` 表是否生成记录
- [ ] 对评论点踩后生成反向偏好
- [ ] 多次相同反馈后 `confidence` 递增
- [ ] 禁用偏好后 Prompt 中不出现
- [ ] 手动添加偏好后触发新评审，检查 LLM 日志中包含偏好上下文
- [ ] 合并重复偏好后减少重复条目
