# Monorepo 结构重组与代码分层改造 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将项目重组为 `apps/backend/` + `apps/frontend/` monorepo 结构，拆分超大文件，建立前后端分层规范。

**Architecture:** 顶层仅做编排，业务代码各自独立于 `apps/backend/`（Python FastAPI）和 `apps/frontend/`（Vue 3）。后端 `management.py`（473行）按资源拆分为 `projects.py` + `reviews.py`，`response_parser.py`（744行）按格式拆分为 5 个独立解析器模块。

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy async, Celery, Vue 3, Vite, Element Plus, git mv（保留历史）

---

## 文件变更地图

### 新增文件
- `apps/backend/src/code_review/api/projects.py`
- `apps/backend/src/code_review/api/reviews.py`
- `apps/backend/src/code_review/infrastructure/response_parser/__init__.py`
- `apps/backend/src/code_review/infrastructure/response_parser/base.py`
- `apps/backend/src/code_review/infrastructure/response_parser/json_parser.py`
- `apps/backend/src/code_review/infrastructure/response_parser/anthropic_parser.py`
- `apps/backend/src/code_review/infrastructure/response_parser/xml_parser.py`
- `apps/backend/src/code_review/infrastructure/response_parser/plain_text_parser.py`
- `apps/frontend/src/api/projects.js`
- `apps/frontend/src/api/reviews.js`
- `apps/frontend/src/api/platforms.js`
- `apps/frontend/src/api/llmConfigs.js`
- `apps/frontend/src/api/templates.js`

### 删除文件
- `src/`（整体迁移到 `apps/backend/src/`）
- `tests/`（整体迁移到 `apps/backend/tests/`）
- `configs/`（整体迁移到 `apps/backend/configs/`）
- `migrations/`（合并到 `apps/backend/migrations/`）
- `frontend/`（整体迁移到 `apps/frontend/`）
- `Dockerfile`（迁移到 `apps/backend/Dockerfile`）
- `pyproject.toml`（迁移到 `apps/backend/pyproject.toml`）
- `uv.lock`（迁移到 `apps/backend/uv.lock`）
- `apps/backend/src/code_review/api/management.py`（拆分后删除）
- `apps/backend/src/code_review/infrastructure/response_parser.py`（拆分后删除）
- 前端 `api/project.js`、`api/review.js`、`api/platform.js`、`api/llm.js`、`api/template.js`

### 修改文件
- `docker/docker-compose.yml`（路径更新）
- `apps/backend/src/code_review/api/app.py`（router 引用更新）

---

## Task 1：创建 apps/ 目录骨架

**Files:**
- Create: `apps/backend/`（目录）
- Create: `apps/frontend/`（目录）
- Create: `apps/backend/migrations/`（目录）

- [ ] **Step 1: 创建 monorepo 顶层目录**

```bash
mkdir -p apps/backend apps/frontend apps/backend/migrations
```

- [ ] **Step 2: 验证目录结构**

```bash
ls apps/
```

期望输出：
```
backend  frontend
```

- [ ] **Step 3: 提交目录骨架**

```bash
git add apps/
git commit -m "chore: 创建 monorepo apps/ 目录骨架"
```

---

## Task 2：迁移后端文件

**Files:**
- Move: `src/` → `apps/backend/src/`
- Move: `tests/` → `apps/backend/tests/`
- Move: `configs/` → `apps/backend/configs/`
- Move: `Dockerfile` → `apps/backend/Dockerfile`
- Move: `pyproject.toml` → `apps/backend/pyproject.toml`
- Move: `uv.lock` → `apps/backend/uv.lock`

- [ ] **Step 1: 用 git mv 迁移后端核心代码（保留 git 历史）**

```bash
git mv src apps/backend/src
git mv tests apps/backend/tests
git mv configs apps/backend/configs
git mv Dockerfile apps/backend/Dockerfile
git mv pyproject.toml apps/backend/pyproject.toml
git mv uv.lock apps/backend/uv.lock
```

- [ ] **Step 2: 合并迁移脚本到统一目录**

```bash
# configs/migrations 已随 configs/ 迁移，补充根目录的孤立迁移文件
cp migrations/002_add_llm_configs.sql apps/backend/migrations/006_add_llm_configs.sql
git add apps/backend/migrations/006_add_llm_configs.sql
```

- [ ] **Step 3: 删除根目录的旧 migrations 目录**

```bash
git rm -r migrations/
```

- [ ] **Step 4: 验证后端目录结构**

```bash
ls apps/backend/
```

期望输出包含：`src  tests  configs  migrations  Dockerfile  pyproject.toml  uv.lock`

- [ ] **Step 5: 验证 pyproject.toml 路径配置仍然正确**

pyproject.toml 中以下配置均为相对路径，迁移后相对 `apps/backend/` 路径不变，无需修改：

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/code_review"]   # 相对 apps/backend/ 正确

[tool.pytest.ini_options]
testpaths = ["tests"]             # 相对 apps/backend/ 正确
pythonpath = ["src"]              # 相对 apps/backend/ 正确
```

- [ ] **Step 6: 在 apps/backend/ 下运行测试，确认全部通过**

```bash
cd apps/backend && python -m pytest tests/ -v
```

期望：所有测试通过（0 failures）

- [ ] **Step 7: 提交后端迁移**

```bash
cd ..  # 回到项目根目录
git add .
git commit -m "chore: 迁移后端代码至 apps/backend/"
```

---

## Task 3：迁移前端文件

**Files:**
- Move: `frontend/` → `apps/frontend/`

- [ ] **Step 1: 用 git mv 迁移前端代码**

```bash
git mv frontend apps/frontend
```

- [ ] **Step 2: 验证前端目录结构**

```bash
ls apps/frontend/
```

期望输出包含：`src  package.json  vite.config.js  index.html`

- [ ] **Step 3: 提交前端迁移**

```bash
git add .
git commit -m "chore: 迁移前端代码至 apps/frontend/"
```

---

## Task 4：更新构建配置

**Files:**
- Modify: `docker/docker-compose.yml`

- [ ] **Step 1: 更新 docker-compose.yml 中的所有路径引用**

将 `docker/docker-compose.yml` 完整替换为：

```yaml
services:
  # ---- FastAPI 应用 ----
  app:
    build:
      context: ../apps/backend
      dockerfile: Dockerfile
    container_name: code-review-app
    ports:
      - "8000:8000"
    env_file:
      - ../apps/backend/configs/.env
    environment:
      - CODE_REVIEW__DATABASE__URL=postgresql+asyncpg://postgres:postgres@db:5432/code_review
      - CODE_REVIEW__REDIS__URL=redis://redis:6379/0
      - CODE_REVIEW__CELERY__BROKER_URL=redis://redis:6379/1
      - CODE_REVIEW__CELERY__RESULT_BACKEND=redis://redis:6379/2
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  # ---- Celery Worker ----
  worker:
    build:
      context: ../apps/backend
      dockerfile: Dockerfile
    container_name: code-review-worker
    command: ["celery", "-A", "code_review.worker", "worker", "-Q", "review", "-l", "info", "--concurrency=2"]
    env_file:
      - ../apps/backend/configs/.env
    environment:
      - CODE_REVIEW__DATABASE__URL=postgresql+asyncpg://postgres:postgres@db:5432/code_review
      - CODE_REVIEW__REDIS__URL=redis://redis:6379/0
      - CODE_REVIEW__CELERY__BROKER_URL=redis://redis:6379/1
      - CODE_REVIEW__CELERY__RESULT_BACKEND=redis://redis:6379/2
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  # ---- PostgreSQL ----
  db:
    image: postgres:16-alpine
    container_name: code-review-db
    environment:
      POSTGRES_DB: code_review
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ../apps/backend/migrations/001_init.sql:/docker-entrypoint-initdb.d/001_init.sql
      - ../apps/backend/migrations/002_prompt_templates.sql:/docker-entrypoint-initdb.d/002_prompt_templates.sql
      - ../apps/backend/migrations/003_platform_and_notification_configs.sql:/docker-entrypoint-initdb.d/003_platform_and_notification_configs.sql
      - ../apps/backend/migrations/004_add_response_format.sql:/docker-entrypoint-initdb.d/004_add_response_format.sql
      - ../apps/backend/migrations/005_add_project_prompt_bindings.sql:/docker-entrypoint-initdb.d/005_add_project_prompt_bindings.sql
      - ../apps/backend/migrations/006_add_llm_configs.sql:/docker-entrypoint-initdb.d/006_add_llm_configs.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # ---- Redis ----
  redis:
    image: redis:7-alpine
    container_name: code-review-redis
    ports:
      - "6380:6379"
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  pgdata:
  redisdata:
```

- [ ] **Step 2: 验证 docker-compose.yml 语法**

```bash
cd docker && docker compose config --quiet && echo "配置验证通过"
```

期望输出：`配置验证通过`

- [ ] **Step 3: 提交构建配置更新**

```bash
cd ..
git add docker/docker-compose.yml
git commit -m "chore: 更新 docker-compose.yml 路径至 apps/ monorepo 结构"
```

---

## Task 5：拆分 management.py → projects.py + reviews.py

**Files:**
- Create: `apps/backend/src/code_review/api/projects.py`
- Create: `apps/backend/src/code_review/api/reviews.py`
- Modify: `apps/backend/src/code_review/api/app.py`
- Delete: `apps/backend/src/code_review/api/management.py`

- [ ] **Step 1: 创建 projects.py（项目 CRUD）**

新建 `apps/backend/src/code_review/api/projects.py`：

```python
"""项目管理 API 端点。"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, Field, ConfigDict

from code_review.models.db import Project

router = APIRouter(prefix="/api/v1", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    platform: str = Field(..., pattern=r"^(github|gitlab|gitee)$")
    platform_project_id: str = Field(..., min_length=1)
    webhook_secret: str = ""
    config: dict | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    webhook_secret: str | None = None
    config: dict | None = None
    enabled: int | None = Field(None, ge=0, le=1)


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    platform: str
    platform_project_id: str
    enabled: int
    config: dict | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(body: ProjectCreate, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        project = Project(
            name=body.name,
            platform=body.platform,
            platform_project_id=body.platform_project_id,
            webhook_secret=body.webhook_secret,
            config=body.config,
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)
        return project


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    request: Request,
    enabled: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    limit: int | None = Query(default=None),
    offset: int | None = Query(default=None),
):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        from sqlalchemy import select
        stmt = select(Project).order_by(Project.created_at.desc())
        if enabled is not None and enabled != "":
            try:
                stmt = stmt.where(Project.enabled == int(enabled))
            except ValueError:
                pass
        if keyword:
            stmt = stmt.where(Project.name.ilike(f"%{keyword}%"))
        if platform:
            stmt = stmt.where(Project.platform == platform)
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        result = await session.execute(stmt)
        return result.scalars().all()


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: UUID, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        project = await session.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return project


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: UUID, body: ProjectUpdate, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        project = await session.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        if body.name is not None:
            project.name = body.name
        if body.webhook_secret is not None:
            project.webhook_secret = body.webhook_secret
        if body.config is not None:
            project.config = body.config
        if body.enabled is not None:
            project.enabled = body.enabled
        project.updated_at = datetime.now(tz=timezone.utc)
        await session.commit()
        await session.refresh(project)
        return project


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: UUID, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        project = await session.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        await session.delete(project)
        await session.commit()
```

- [ ] **Step 2: 创建 reviews.py（评审任务 + 健康检查）**

新建 `apps/backend/src/code_review/api/reviews.py`：

```python
"""评审任务 API 端点及系统健康检查。"""

import logging
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, func, delete as sql_delete

from code_review.models.db import Project, ReviewTask, ReviewComment
from code_review.infrastructure.cache import event_dedup_cache
from code_review.adapters.factory import create_adapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["reviews"])


class ReviewTaskResponse(BaseModel):
    id: UUID
    project_id: UUID
    mr_iid: str
    mr_title: str | None
    mr_author: str | None
    mr_url: str | None
    status: str
    trigger_action: str | None
    model_name: str | None
    total_comments: int | None
    critical_count: int | None
    warning_count: int | None
    summary: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewCommentResponse(BaseModel):
    id: UUID
    task_id: UUID
    file_path: str
    line_start: int
    line_end: int | None
    severity: str
    message: str
    suggestion: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeleteReviewsRequest(BaseModel):
    task_ids: list[UUID] = Field(..., min_length=1, max_length=100)


class DeleteReviewsByDateRequest(BaseModel):
    start_date: datetime = Field(..., description="开始日期")
    end_date: datetime = Field(..., description="结束日期")
    project_id: UUID | None = None


class ManualReviewRequest(BaseModel):
    project_id: UUID = Field(..., description="项目 ID")
    mr_iid: str = Field(..., min_length=1, max_length=64, description="MR 短 ID")
    trigger_action: str = Field(default="manual", description="触发动作标识")


@router.get("/reviews", response_model=list[ReviewTaskResponse])
async def list_reviews(
    request: Request,
    project_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        stmt = select(ReviewTask).order_by(ReviewTask.created_at.desc())
        if project_id:
            stmt = stmt.where(ReviewTask.project_id == UUID(project_id))
        if status:
            stmt = stmt.where(ReviewTask.status == status)
        stmt = stmt.offset(offset).limit(min(limit, 100))
        result = await session.execute(stmt)
        return result.scalars().all()


@router.get("/reviews/{task_id}", response_model=ReviewTaskResponse)
async def get_review(task_id: UUID, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        task = await session.get(ReviewTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Review task not found")
        return task


@router.get("/reviews/{task_id}/comments", response_model=list[ReviewCommentResponse])
async def get_review_comments(task_id: UUID, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        stmt = (
            select(ReviewComment)
            .where(ReviewComment.task_id == task_id)
            .order_by(ReviewComment.file_path, ReviewComment.line_start)
        )
        result = await session.execute(stmt)
        return result.scalars().all()


@router.delete("/reviews/all", status_code=204)
async def clear_all_reviews(request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        stmt = select(ReviewTask.event_id).where(ReviewTask.event_id.isnot(None))
        result = await session.execute(stmt)
        event_ids = [row[0] for row in result.all()]
        for event_id in event_ids:
            event_dedup_cache.delete(event_id)
        await session.execute(sql_delete(ReviewTask))
        await session.commit()
        event_dedup_cache.clear()
        logger.info(f"清空所有评审记录: {len(event_ids)} 条")


@router.delete("/reviews/{task_id}", status_code=204)
async def delete_review(task_id: UUID, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        task = await session.get(ReviewTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="评审记录不存在")
        if task.event_id:
            event_dedup_cache.delete(task.event_id)
        await session.delete(task)
        await session.commit()
        logger.info(f"删除评审记录: {task_id}")


@router.post("/reviews/batch-delete", status_code=204)
async def batch_delete_reviews(body: DeleteReviewsRequest, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        stmt = select(ReviewTask).where(ReviewTask.id.in_(body.task_ids))
        result = await session.execute(stmt)
        tasks = result.scalars().all()
        if not tasks:
            raise HTTPException(status_code=404, detail="未找到指定的评审记录")
        for task in tasks:
            if task.event_id:
                event_dedup_cache.delete(task.event_id)
        for task in tasks:
            await session.delete(task)
        await session.commit()
        logger.info(f"批量删除评审记录: {len(tasks)} 条")


@router.post("/reviews/delete-by-date", status_code=204)
async def delete_reviews_by_date(body: DeleteReviewsByDateRequest, request: Request):
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        stmt = select(ReviewTask).where(
            ReviewTask.created_at >= body.start_date,
            ReviewTask.created_at <= body.end_date + timedelta(days=1),
        )
        if body.project_id:
            stmt = stmt.where(ReviewTask.project_id == body.project_id)
        result = await session.execute(stmt)
        tasks = result.scalars().all()
        if not tasks:
            raise HTTPException(status_code=404, detail="指定日期范围内没有评审记录")
        for task in tasks:
            if task.event_id:
                event_dedup_cache.delete(task.event_id)
        for task in tasks:
            await session.delete(task)
        await session.commit()
        logger.info(f"按日期删除评审记录: {len(tasks)} 条")


@router.post("/reviews/manual", response_model=ReviewTaskResponse, status_code=201)
async def create_manual_review(
    body: ManualReviewRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    session_factory = request.app.state.session_factory
    orchestrator = request.app.state.orchestrator

    async with session_factory() as session:
        project = await session.get(Project, body.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        if not project.enabled:
            raise HTTPException(status_code=400, detail="项目未启用")

        event_id = f"manual_{body.project_id}_{body.mr_iid}"
        stmt = select(ReviewTask).where(
            ReviewTask.project_id == body.project_id,
            ReviewTask.mr_iid == body.mr_iid,
            ReviewTask.event_id == event_id,
        )
        if (await session.execute(stmt)).scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail="该 MR 已存在评审记录，请先删除原有记录后再手动触发",
            )

        platform_config = await orchestrator._get_platform_config(project.platform)
        if not platform_config:
            raise HTTPException(status_code=400, detail=f"未配置 {project.platform} 平台信息")

        adapter = create_adapter(
            platform=project.platform,
            platform_config=platform_config,
            project_webhook_secret=project.webhook_secret or "",
        )
        try:
            mr_info = await adapter.get_mr_info(project.platform_project_id, body.mr_iid)
        except Exception as e:
            logger.error(f"获取 MR 信息失败: {e}")
            raise HTTPException(status_code=400, detail=f"获取 MR 信息失败: {str(e)}")

        task = ReviewTask(
            project_id=body.project_id,
            mr_iid=body.mr_iid,
            trigger_action=body.trigger_action,
            event_id=event_id,
            mr_title=mr_info.title,
            mr_author=mr_info.author,
            mr_url=mr_info.web_url or mr_info.url,
            source_branch=mr_info.source_branch,
            target_branch=mr_info.target_branch,
            status=ReviewTask.Status.PENDING,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)

    async def run_review():
        try:
            await orchestrator.execute_review(str(task.id))
        except Exception as e:
            logger.error(f"手动评审失败: {e}")

    background_tasks.add_task(run_review)
    logger.info(f"创建手动评审任务: {task.id}")
    return task


@router.get("/health")
async def health_check(request: Request):
    checks = {"database": False}
    try:
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            await session.execute(select(func.count()).select_from(Project))
            checks["database"] = True
    except Exception as e:
        logger.error("Database health check failed: %s", e)

    notification_manager = request.app.state.notification_manager
    checks["notifications"] = await notification_manager.health_check()

    all_healthy = all(
        v if isinstance(v, bool) else all(v.values())
        for v in checks.values()
    )
    return {"status": "healthy" if all_healthy else "degraded", "checks": checks}
```

- [ ] **Step 3: 更新 app.py 的 router 引用**

修改 `apps/backend/src/code_review/api/app.py` 第 12 行，将：

```python
from code_review.api.management import router as management_router
```

替换为：

```python
from code_review.api.projects import router as projects_router
from code_review.api.reviews import router as reviews_router
```

同时将第 125 行：

```python
    app.include_router(management_router)
```

替换为：

```python
    app.include_router(projects_router)
    app.include_router(reviews_router)
```

- [ ] **Step 4: 删除 management.py**

```bash
git rm apps/backend/src/code_review/api/management.py
```

- [ ] **Step 5: 运行测试验证拆分正确**

```bash
cd apps/backend && python -m pytest tests/ -v
```

期望：所有测试通过

- [ ] **Step 6: 运行 ruff 检查**

```bash
cd apps/backend && python -m ruff check src/
```

期望：无报错

- [ ] **Step 7: 提交 management.py 拆分**

```bash
cd ..
git add apps/backend/src/code_review/api/
git commit -m "refactor: 拆分 management.py 为 projects.py + reviews.py"
```

---

## Task 6：拆分 response_parser.py → response_parser/ 包

**Files:**
- Create: `apps/backend/src/code_review/infrastructure/response_parser/__init__.py`
- Create: `apps/backend/src/code_review/infrastructure/response_parser/base.py`
- Create: `apps/backend/src/code_review/infrastructure/response_parser/json_parser.py`
- Create: `apps/backend/src/code_review/infrastructure/response_parser/anthropic_parser.py`
- Create: `apps/backend/src/code_review/infrastructure/response_parser/xml_parser.py`
- Create: `apps/backend/src/code_review/infrastructure/response_parser/plain_text_parser.py`
- Delete: `apps/backend/src/code_review/infrastructure/response_parser.py`

- [ ] **Step 1: 创建包目录**

```bash
mkdir -p apps/backend/src/code_review/infrastructure/response_parser
```

- [ ] **Step 2: 创建 base.py（共享类型 + 工具函数）**

新建 `apps/backend/src/code_review/infrastructure/response_parser/base.py`：

```python
"""响应解析器基础类型、枚举和共享工具函数。"""

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum

from code_review.core.llm import ReviewComment, Severity

logger = logging.getLogger(__name__)


class ResponseFormat(StrEnum):
    AUTO = "auto"
    JSON = "json"
    ANTHROPIC_THINKING = "anthropic_thinking"
    XML = "xml"
    PLAIN_TEXT = "plain_text"
    UNKNOWN = "unknown"


@dataclass
class ParsedReview:
    comments: list[ReviewComment]
    summary: str
    format_used: ResponseFormat
    raw_content: str
    warnings: list[str] = field(default_factory=list)


class ResponseParser(ABC):
    @abstractmethod
    def can_parse(self, content: str) -> bool:
        pass

    @abstractmethod
    def parse(self, content: str) -> ParsedReview:
        pass


def extract_json_block(content: str) -> str:
    json_str = content.strip()
    if json_str.startswith('{') or json_str.startswith('['):
        return json_str
    if "```json" in content:
        parts = content.split("```json", 1)
        if len(parts) > 1:
            json_str = parts[1].split("```", 1)[0]
    elif "```" in content:
        parts = content.split("```", 1)
        if len(parts) > 1:
            json_str = parts[1].split("```", 1)[0]
    return json_str.strip()


def fix_unescaped_newlines(json_str: str) -> tuple[str, int]:
    result = []
    i = 0
    n = len(json_str)
    in_string = False
    escape_next = False
    fixed_count = 0

    while i < n:
        char = json_str[i]
        if escape_next:
            result.append(char)
            escape_next = False
        elif char == '\\':
            result.append(char)
            escape_next = True
        elif char == '"':
            result.append(char)
            in_string = not in_string
        elif in_string and char in '\n\r\t':
            if char == '\n':
                result.append('\\n')
            elif char == '\r':
                result.append('\\r')
            elif char == '\t':
                result.append('\\t')
            fixed_count += 1
        else:
            result.append(char)
        i += 1

    return ''.join(result), fixed_count


def fix_truncated_json(json_str: str) -> tuple[str, int]:
    fixes = 0
    in_string = False
    escape_next = False

    for i in range(len(json_str) - 1, -1, -1):
        char = json_str[i]
        if escape_next:
            escape_next = False
            continue
        if char == '\\':
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            if not in_string:
                break

    if in_string:
        logger.info("检测到未闭合的字符串，尝试截断到上一个完整位置")
        last_brace_pos = json_str.rfind('}')
        if last_brace_pos != -1:
            second_last_brace = json_str.rfind('}', 0, last_brace_pos)
            if second_last_brace != -1:
                json_str = json_str[:second_last_brace + 1]
                fixes += 100
                logger.info(f"截断 JSON 到位置 {second_last_brace}")

    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    open_brackets = json_str.count('[')
    close_brackets = json_str.count(']')

    if open_braces > close_braces:
        json_str += '}' * (open_braces - close_braces)
        fixes += open_braces - close_braces
    if open_brackets > close_brackets:
        json_str += ']' * (open_brackets - close_brackets)
        fixes += open_brackets - close_brackets

    return json_str, fixes


def fix_json_string(content: str) -> tuple[str, list[str]]:
    warnings = []
    json_str = extract_json_block(content)
    json_str, newline_fixes = fix_unescaped_newlines(json_str)
    if newline_fixes > 0:
        warnings.append(f"修复了 {newline_fixes} 处未转义的换行符")
    if json_str.startswith('\ufeff'):
        json_str = json_str[1:]
        warnings.append("移除了 BOM 标记")
    json_str, truncation_fixes = fix_truncated_json(json_str)
    if truncation_fixes > 0:
        warnings.append(f"修复了 {truncation_fixes} 处未闭合的括号")
    return json_str, warnings


def parse_comments_list(comments_data: list) -> tuple[list[ReviewComment], list[str]]:
    warnings = []
    comments = []
    for item in comments_data:
        try:
            file_path = item.get("file_path") or item.get("path") or ""
            line_start = item.get("line_start") or item.get("line", 1)
            line_end = item.get("line_end") or item.get("line", line_start)
            message = item.get("message") or item.get("comment") or item.get("text") or ""
            suggestion = item.get("suggestion") or ""
            severity_str = item.get("severity", "suggestion").lower()
            try:
                severity = Severity(severity_str)
            except ValueError:
                severity = Severity.SUGGESTION
                warnings.append(f"未知的严重程度: {severity_str}")
            comments.append(ReviewComment(
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                severity=severity,
                message=message,
                suggestion=suggestion,
            ))
        except Exception as e:
            warnings.append(f"跳过无效评论: {e}")
    return comments, warnings
```

- [ ] **Step 3: 创建 json_parser.py**

新建 `apps/backend/src/code_review/infrastructure/response_parser/json_parser.py`：

```python
"""JSON 格式 LLM 响应解析器。"""

import json
import logging

from .base import ResponseParser, ParsedReview, ResponseFormat, fix_json_string, parse_comments_list

logger = logging.getLogger(__name__)


class JSONParser(ResponseParser):
    def can_parse(self, content: str) -> bool:
        content_stripped = content.strip()
        return (
            content_stripped.startswith("{") or
            content_stripped.startswith("[") or
            "```json" in content or
            "```" in content
        )

    def parse(self, content: str) -> ParsedReview:
        warnings = []
        json_str, fix_warnings = fix_json_string(content)
        warnings.extend(fix_warnings)
        logger.info(f"JSON 修复完成，内容长度: {len(json_str)}")

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            data = self._try_partial_parse(json_str, warnings)
            if data is None:
                logger.warning("完全无法解析 JSON，返回空结果")
                return ParsedReview(
                    comments=[],
                    summary="JSON 解析完全失败，无法提取评审意见",
                    format_used=ResponseFormat.JSON,
                    raw_content=content,
                    warnings=[f"JSON 解析失败: {e}", "返回了空结果"],
                )

        summary = data.get("summary", "") if isinstance(data, dict) else ""
        if not summary:
            summary = "无法提取摘要"
        comments_data = data.get("comments", []) if isinstance(data, dict) else []
        if not isinstance(comments_data, list):
            comments_data = []

        comments, parse_warnings = parse_comments_list(comments_data)
        warnings.extend(parse_warnings)
        logger.info(f"JSON 解析成功: {len(comments)} 条评审意见")
        return ParsedReview(
            comments=comments,
            summary=summary,
            format_used=ResponseFormat.JSON,
            raw_content=content,
            warnings=warnings,
        )

    def _try_partial_parse(self, json_str: str, warnings: list[str]) -> dict | None:
        try:
            comments_start = json_str.find('"comments"')
            if comments_start == -1:
                return None
            array_start = json_str.find('[', comments_start)
            if array_start == -1:
                return None

            stack = []
            complete_objects = []
            current_obj_start = -1
            in_string = False
            escape_next = False

            for i in range(array_start, len(json_str)):
                char = json_str[i]
                if escape_next:
                    escape_next = False
                    continue
                if char == '\\' and in_string:
                    escape_next = True
                    continue
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if char == '{':
                    if not stack:
                        current_obj_start = i
                    stack.append('{')
                elif char == '}':
                    if stack and stack[-1] == '{':
                        stack.pop()
                        if not stack:
                            obj_str = json_str[current_obj_start:i + 1]
                            try:
                                complete_objects.append(json.loads(obj_str))
                            except json.JSONDecodeError:
                                pass
                elif char == '[':
                    stack.append('[')
                elif char == ']':
                    if stack and stack[-1] == '[':
                        stack.pop()
                        if not stack:
                            break

            if complete_objects:
                warnings.append(f"从截断响应中提取了 {len(complete_objects)} 条完整评论")
                return {"summary": "响应被截断，仅包含部分评审意见", "comments": complete_objects}
            return None
        except Exception as e:
            logger.warning(f"部分解析异常: {e}")
            return None
```

- [ ] **Step 4: 创建 anthropic_parser.py**

新建 `apps/backend/src/code_review/infrastructure/response_parser/anthropic_parser.py`：

```python
"""Anthropic thinking 格式 LLM 响应解析器。"""

import json
import logging

from .base import ResponseParser, ParsedReview, ResponseFormat, parse_comments_list

logger = logging.getLogger(__name__)


class AnthropicThinkingParser(ResponseParser):
    def can_parse(self, content: str) -> bool:
        keywords = ["thinking", "reasoning_content", "thinking_blocks", "<thinking>"]
        content_lower = content.lower()
        return any(k in content_lower for k in keywords)

    def parse(self, content: str) -> ParsedReview:
        warnings = []
        comments = []
        summary = ""

        try:
            data = self._extract_json(content)
            if isinstance(data, dict):
                summary = data.get("summary", "")
                if any(k in data for k in ["thinking", "reasoning_content", "thinking_blocks"]):
                    warnings.append("检测到 thinking blocks，已忽略推理过程")
                comments_data = data.get("comments", [])
                if not comments_data and "content" in data:
                    for block in data["content"]:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if text:
                                try:
                                    embedded = json.loads(text)
                                    if "comments" in embedded:
                                        comments_data = embedded["comments"]
                                        if not summary:
                                            summary = embedded.get("summary", "")
                                        break
                                except json.JSONDecodeError:
                                    pass
                comments, parse_warnings = parse_comments_list(comments_data)
                warnings.extend(parse_warnings)

            logger.info(f"Anthropic 格式解析成功: {len(comments)} 条评审意见")
            return ParsedReview(
                comments=comments,
                summary=summary,
                format_used=ResponseFormat.ANTHROPIC_THINKING,
                raw_content=content,
                warnings=warnings,
            )
        except Exception as e:
            logger.error(f"Anthropic 格式解析失败: {e}")
            raise

    def _extract_json(self, content: str) -> dict:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        if "```json" in content:
            return json.loads(content.split("```json", 1)[1].split("```", 1)[0].strip())
        elif "```" in content:
            return json.loads(content.split("```", 1)[1].split("```", 1)[0].strip())
        raise ValueError("无法提取有效的 JSON")
```

- [ ] **Step 5: 创建 xml_parser.py**

新建 `apps/backend/src/code_review/infrastructure/response_parser/xml_parser.py`：

```python
"""XML 格式 LLM 响应解析器。"""

import logging
import xml.etree.ElementTree as ET

from code_review.core.llm import ReviewComment, Severity
from .base import ResponseParser, ParsedReview, ResponseFormat

logger = logging.getLogger(__name__)


class XMLParser(ResponseParser):
    def can_parse(self, content: str) -> bool:
        content_stripped = content.strip()
        return (
            content_stripped.startswith("<?xml") or
            (content_stripped.startswith("<") and ("</" in content or "/>" in content))
        )

    def parse(self, content: str) -> ParsedReview:
        warnings = []
        comments = []
        summary = ""

        try:
            xml_str = content.strip()
            if "```xml" in content:
                xml_str = content.split("```xml", 1)[1].split("```", 1)[0].strip()
            elif "```" in content:
                xml_str = content.split("```", 1)[1].split("```", 1)[0].strip()

            root = ET.fromstring(xml_str)
            summary_elem = root.find("summary")
            if summary_elem is not None and summary_elem.text:
                summary = summary_elem.text

            comments_elem = root.find("comments")
            if comments_elem is not None:
                for comment_elem in comments_elem.findall("comment"):
                    severity_str = comment_elem.get("severity", "suggestion").lower()
                    try:
                        severity = Severity(severity_str)
                    except ValueError:
                        severity = Severity.SUGGESTION
                        warnings.append(f"未知的严重程度: {severity_str}")

                    line_start = int(comment_elem.get("line_start", 1))
                    line_end = int(comment_elem.get("line_end", comment_elem.get("line_start", 1)))
                    comments.append(ReviewComment(
                        file_path=comment_elem.get("file_path", ""),
                        line_start=line_start,
                        line_end=line_end,
                        severity=severity,
                        message=comment_elem.findtext("message", ""),
                        suggestion=comment_elem.findtext("suggestion", ""),
                    ))

            logger.info(f"XML 解析成功: {len(comments)} 条评审意见")
            return ParsedReview(
                comments=comments,
                summary=summary,
                format_used=ResponseFormat.XML,
                raw_content=content,
                warnings=warnings,
            )
        except ET.ParseError as e:
            logger.error(f"XML 解析失败: {e}")
            raise ValueError(f"XML 解析失败: {e}")
```

- [ ] **Step 6: 创建 plain_text_parser.py**

新建 `apps/backend/src/code_review/infrastructure/response_parser/plain_text_parser.py`：

```python
"""纯文本格式 LLM 响应解析器（正则提取，降级方案）。"""

import logging
import re

from code_review.core.llm import ReviewComment, Severity
from .base import ResponseParser, ParsedReview, ResponseFormat

logger = logging.getLogger(__name__)


class PlainTextParser(ResponseParser):
    COMMENT_PATTERN = re.compile(
        r'(?:文件|file|路径|path)[:\s]+([^\n\r]+)[\r\n]+'
        r'(?:行|line)[:\s]+(\d+)(?:-(\d+))?[\r\n]+'
        r'(?:严重程度|severity|级别)[:\s]+(\w+)[\r\n]+'
        r'(?:意见|message|描述|description)[:\s]+([^\n\r]+)(?:[\r\n]+'
        r'(?:建议|suggestion)[:\s]+([^\n\r]+))?',
        re.IGNORECASE,
    )
    SUMMARY_PATTERN = re.compile(
        r'(?:摘要|summary|总结)[:\s]+([^\n\r]+)',
        re.IGNORECASE,
    )

    def can_parse(self, content: str) -> bool:
        return True

    def parse(self, content: str) -> ParsedReview:
        warnings = ["使用纯文本解析器（正则提取），准确性可能降低"]
        comments = []
        summary = ""

        summary_match = self.SUMMARY_PATTERN.search(content)
        if summary_match:
            summary = summary_match.group(1).strip()

        for match in self.COMMENT_PATTERN.finditer(content):
            try:
                file_path = match.group(1).strip()
                line_start = int(match.group(2))
                line_end = int(match.group(3)) if match.group(3) else line_start
                severity_str = match.group(4).lower()
                message = match.group(5).strip()
                suggestion = match.group(6).strip() if match.group(6) else ""
                try:
                    severity = Severity(severity_str)
                except ValueError:
                    severity = Severity.SUGGESTION
                if line_start > 0 and file_path:
                    comments.append(ReviewComment(
                        file_path=file_path,
                        line_start=line_start,
                        line_end=line_end,
                        severity=severity,
                        message=message,
                        suggestion=suggestion,
                    ))
            except (ValueError, AttributeError) as e:
                warnings.append(f"跳过无效的评论匹配: {e}")

        if not comments:
            warnings.append("未能从文本中提取任何评审意见")
            raise ValueError("纯文本解析器未能提取任何评审意见")

        logger.info(f"纯文本解析完成: {len(comments)} 条评审意见")
        return ParsedReview(
            comments=comments,
            summary=summary,
            format_used=ResponseFormat.PLAIN_TEXT,
            raw_content=content,
            warnings=warnings,
        )
```

- [ ] **Step 7: 创建 __init__.py（保持调用方零改动）**

新建 `apps/backend/src/code_review/infrastructure/response_parser/__init__.py`：

```python
"""多格式 LLM 响应解析器包。

对外导出与原 response_parser.py 完全兼容的接口，调用方无需修改 import 语句。
"""

import logging

from code_review.core.llm import ReviewComment

from .base import ResponseFormat, ParsedReview, ResponseParser
from .json_parser import JSONParser
from .anthropic_parser import AnthropicThinkingParser
from .xml_parser import XMLParser
from .plain_text_parser import PlainTextParser

logger = logging.getLogger(__name__)


class MultiFormatResponseParser:
    """多格式响应解析器（自动检测格式并路由）。"""

    def __init__(self):
        self._parsers = [
            AnthropicThinkingParser(),
            XMLParser(),
            JSONParser(),
            PlainTextParser(),
        ]
        self._format_parser_map = {
            ResponseFormat.JSON: JSONParser(),
            ResponseFormat.ANTHROPIC_THINKING: AnthropicThinkingParser(),
            ResponseFormat.XML: XMLParser(),
            ResponseFormat.PLAIN_TEXT: PlainTextParser(),
        }

    def parse(self, content: str, format_hint: ResponseFormat = ResponseFormat.AUTO) -> ParsedReview:
        logger.info(f"=== 多格式解析器开始 === 内容长度: {len(content)}, 格式提示: {format_hint}")

        if format_hint != ResponseFormat.AUTO and format_hint in self._format_parser_map:
            parser = self._format_parser_map[format_hint]
            logger.info(f"使用指定格式解析器: {parser.__class__.__name__}")
            try:
                result = parser.parse(content)
                self._log_result(result)
                return result
            except Exception as e:
                logger.error(f"指定格式解析器失败: {e}，降级到自动检测")

        for parser in self._parsers:
            try:
                if parser.can_parse(content):
                    logger.info(f"尝试 {parser.__class__.__name__}")
                    result = parser.parse(content)
                    self._log_result(result)
                    return result
            except Exception as e:
                logger.info(f"{parser.__class__.__name__} 失败: {e}")
                continue

        error_msg = "所有解析器都无法解析该响应内容"
        logger.error(error_msg)
        raise ValueError(error_msg)

    def _log_result(self, result: ParsedReview) -> None:
        for warning in result.warnings:
            logger.warning(f"解析警告: {warning}")
        logger.info(
            f"解析成功: 格式={result.format_used.value}, "
            f"评论数={len(result.comments)}, "
            f"摘要长度={len(result.summary)}"
        )

    def parse_with_fallback(
        self,
        content: str,
        fallback_comments: list[ReviewComment] | None = None,
        format_hint: ResponseFormat = ResponseFormat.AUTO,
    ) -> ParsedReview:
        try:
            return self.parse(content, format_hint=format_hint)
        except Exception as e:
            logger.warning(f"解析失败，使用降级方案: {e}")
            return ParsedReview(
                comments=fallback_comments or [],
                summary=f"解析失败: {str(e)}",
                format_used=ResponseFormat.UNKNOWN,
                raw_content=content,
                warnings=[f"解析失败，已使用降级方案: {str(e)}"],
            )


__all__ = [
    "MultiFormatResponseParser",
    "ParsedReview",
    "ResponseFormat",
    "ResponseParser",
    "JSONParser",
    "AnthropicThinkingParser",
    "XMLParser",
    "PlainTextParser",
]
```

- [ ] **Step 8: 删除原始 response_parser.py 文件**

```bash
git rm apps/backend/src/code_review/infrastructure/response_parser.py
```

- [ ] **Step 9: 运行测试验证拆分正确**

```bash
cd apps/backend && python -m pytest tests/test_response_parser.py -v
```

期望：所有测试通过

- [ ] **Step 10: 运行全量测试**

```bash
python -m pytest tests/ -v
```

期望：所有测试通过

- [ ] **Step 11: 运行 ruff 检查**

```bash
python -m ruff check src/
```

期望：无报错

- [ ] **Step 12: 提交 response_parser 拆分**

```bash
cd ..
git add apps/backend/src/code_review/infrastructure/
git commit -m "refactor: 拆分 response_parser.py 为 response_parser/ 包（4个格式解析器）"
```

---

## Task 7：重命名前端 API 模块

**Files:**
- Rename: `apps/frontend/src/api/project.js` → `apps/frontend/src/api/projects.js`
- Rename: `apps/frontend/src/api/review.js` → `apps/frontend/src/api/reviews.js`
- Rename: `apps/frontend/src/api/platform.js` → `apps/frontend/src/api/platforms.js`
- Rename: `apps/frontend/src/api/llm.js` → `apps/frontend/src/api/llmConfigs.js`
- Rename: `apps/frontend/src/api/template.js` → `apps/frontend/src/api/templates.js`
- Modify: 16 个 Vue/JS 文件中的 import 引用

- [ ] **Step 1: 用 git mv 重命名 API 模块文件**

```bash
git mv apps/frontend/src/api/project.js apps/frontend/src/api/projects.js
git mv apps/frontend/src/api/review.js apps/frontend/src/api/reviews.js
git mv apps/frontend/src/api/platform.js apps/frontend/src/api/platforms.js
git mv apps/frontend/src/api/llm.js apps/frontend/src/api/llmConfigs.js
git mv apps/frontend/src/api/template.js apps/frontend/src/api/templates.js
```

- [ ] **Step 2: 批量替换 import 引用（project → projects）**

```bash
# 找出所有引用旧模块名的文件并替换
grep -rl "from.*api/project'" apps/frontend/src | xargs sed -i '' "s|api/project'|api/projects'|g"
grep -rl 'from.*api/project"' apps/frontend/src | xargs sed -i '' 's|api/project"|api/projects"|g'
```

- [ ] **Step 3: 批量替换 import 引用（review → reviews）**

```bash
grep -rl "from.*api/review'" apps/frontend/src | xargs sed -i '' "s|api/review'|api/reviews'|g"
grep -rl 'from.*api/review"' apps/frontend/src | xargs sed -i '' 's|api/review"|api/reviews"|g'
```

- [ ] **Step 4: 批量替换 import 引用（platform → platforms）**

```bash
grep -rl "from.*api/platform'" apps/frontend/src | xargs sed -i '' "s|api/platform'|api/platforms'|g"
grep -rl 'from.*api/platform"' apps/frontend/src | xargs sed -i '' 's|api/platform"|api/platforms"|g'
```

- [ ] **Step 5: 批量替换 import 引用（llm → llmConfigs）**

```bash
grep -rl "from.*api/llm'" apps/frontend/src | xargs sed -i '' "s|api/llm'|api/llmConfigs'|g"
grep -rl 'from.*api/llm"' apps/frontend/src | xargs sed -i '' 's|api/llm"|api/llmConfigs"|g'
```

- [ ] **Step 6: 批量替换 import 引用（template → templates）**

```bash
grep -rl "from.*api/template'" apps/frontend/src | xargs sed -i '' "s|api/template'|api/templates'|g"
grep -rl 'from.*api/template"' apps/frontend/src | xargs sed -i '' 's|api/template"|api/templates"|g'
```

- [ ] **Step 7: 验证无残留旧引用**

```bash
grep -r "api/project'\|api/review'\|api/platform'\|api/llm'\|api/template'" apps/frontend/src
```

期望：无输出（没有残留旧引用）

- [ ] **Step 8: 构建前端验证无编译错误**

```bash
cd apps/frontend && npm run build
```

期望：构建成功，无报错

- [ ] **Step 9: 提交前端 API 重命名**

```bash
cd ../..
git add apps/frontend/src/api/
git add apps/frontend/src/views/
git commit -m "refactor: 重命名前端 API 模块为复数/驼峰命名（projects/reviews/platforms/llmConfigs/templates）"
```

---

## 验收清单

运行以下检查确认全部完成：

```bash
# 1. 目录结构检查
[ -d "apps/backend/src/code_review" ] && echo "✓ backend 目录存在" || echo "✗ backend 目录缺失"
[ -d "apps/frontend/src" ] && echo "✓ frontend 目录存在" || echo "✗ frontend 目录缺失"
[ ! -d "src" ] && echo "✓ 根目录 src/ 已清除" || echo "✗ 根目录 src/ 未清除"

# 2. migrations 检查
ls apps/backend/migrations/ | wc -l | xargs -I{} bash -c '[ {} -eq 6 ] && echo "✓ 迁移文件数量正确(6)" || echo "✗ 迁移文件数量错误({})"'

# 3. API 拆分检查
[ ! -f "apps/backend/src/code_review/api/management.py" ] && echo "✓ management.py 已拆分" || echo "✗ management.py 未拆分"
[ -f "apps/backend/src/code_review/api/projects.py" ] && echo "✓ projects.py 存在" || echo "✗ projects.py 缺失"
[ -f "apps/backend/src/code_review/api/reviews.py" ] && echo "✓ reviews.py 存在" || echo "✗ reviews.py 缺失"

# 4. response_parser 包检查
[ -d "apps/backend/src/code_review/infrastructure/response_parser" ] && echo "✓ response_parser 包存在" || echo "✗ response_parser 包缺失"
[ ! -f "apps/backend/src/code_review/infrastructure/response_parser.py" ] && echo "✓ response_parser.py 已删除" || echo "✗ response_parser.py 未删除"

# 5. 前端 API 模块检查
[ -f "apps/frontend/src/api/projects.js" ] && echo "✓ projects.js 存在" || echo "✗ projects.js 缺失"
[ ! -f "apps/frontend/src/api/llm.js" ] && echo "✓ llm.js 已重命名" || echo "✗ llm.js 未重命名"

# 6. 测试
cd apps/backend && python -m pytest tests/ -q && echo "✓ 所有后端测试通过"

# 7. 代码检查
python -m ruff check src/ && echo "✓ ruff 检查通过"
```
