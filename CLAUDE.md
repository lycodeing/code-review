# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 构建与运行命令

```bash
# 后端：安装依赖（需要 Python >= 3.11）
cd apps/backend
uv pip install -e ".[dev]"

# 启动 FastAPI 服务
cd apps/backend
uvicorn code_review.api.app:app --reload --port 8000

# 启动 Celery Worker（独立终端）
cd apps/backend
celery -A code_review.worker worker -Q review -l info

# 前端：安装依赖并启动开发服务器（:3000）
cd apps/frontend
npm install && npm run dev

# 前端：生产构建
cd apps/frontend && npm run build

# Docker Compose 部署（推荐，保留已有数据库数据）
cd docker && docker compose up -d

# 初始化数据库（本地开发）
psql -U postgres -c "CREATE DATABASE code_review;"
psql -U postgres -d code_review -f apps/backend/migrations/init.sql

# 运行全部测试
cd apps/backend && pytest

# 运行单个测试文件
cd apps/backend && pytest tests/test_comment_aggregator.py -v

# 运行单个测试函数
cd apps/backend && pytest tests/test_adapters.py::TestGitHubAdapter::test_parse_project_id -v

# 代码检查
cd apps/backend && ruff check src/ tests/

# 类型检查
cd apps/backend && mypy src/
```

## 架构概览

Monorepo 结构：`apps/backend/`（Python FastAPI）+ `apps/frontend/`（Vue 3）+ `docker/`（编排）。

评审流水线穿过四层：

```
core/（抽象接口 ABC）
  → adapters/（GitHub / GitLab / Gitee 平台实现）
  → infrastructure/（LLM、通知、缓存、Celery、加解密、response_parser）
  → services/（业务逻辑 + 配置管理）
  → api/（FastAPI 路由）
```

### 核心数据流：Webhook → 评审完成

1. **API 层**（`api/webhook.py`）接收 POST 请求，通过平台适配器验证签名，解析为 `WebhookEvent`
2. **ReviewOrchestrator**（`services/review_orchestrator.py`）通过 TTL 缓存去重，在 PostgreSQL 创建 `ReviewTask`，分发 Celery 任务
3. **Celery Worker**（`worker.py`）调用 `orchestrator.execute_review()`，流程：
   - 读取 `platform_configs` 表获取平台配置（token、api_url），空值降级到 env
   - 通过平台适配器获取 MR 变更文件，按 `exclude_patterns` 过滤
   - 从 `prompt_templates` 表加载 Prompt 模板（热更新，每次评审实时查询）
   - 通过 LiteLLM（`infrastructure/llm_reviewer.py`）调用大模型
   - 聚合评论、发布行内评论、发送通知
   - 更新任务状态：pending → in_progress → completed/failed

### 配置中心（数据库驱动）

- **`platform_configs`** — 代码平台配置（gitee/github/gitlab），含 access_token、webhook_secret、api_url
- **`notification_configs`** — 通知渠道配置（dingtalk/feishu），含 webhook_url、secret、at_mobiles
- **`llm_configs`** — LLM 提供商配置，含 model_name、api_key、api_base、response_format
- **`platform_notification_bindings`** — 平台-通知渠道多对多关联

敏感字段（token、key、secret）通过 `infrastructure/config_crypto.py` 使用 AES-256-GCM 加密，密钥从 `CODE_REVIEW__SERVER__SECRET_KEY` 派生。`PlatformConfigService.get_by_platform_with_fallback()` 优先读 DB，敏感字段为空时降级到 env。

不迁移到 DB 的配置（保持环境变量）：Server、Database、Redis、Celery、Review 行为参数。

### API 路由文件

`apps/backend/src/code_review/api/` 各文件对应独立资源：
- `webhook.py` — Webhook 接收端点（签名验证 + 任务分发）
- `projects.py` — 项目 CRUD + 评审历史
- `reviews.py` — 评审列表 / 详情 / 手动触发
- `platform_config.py` — 平台配置 CRUD
- `notification_config.py` — 通知配置 CRUD + 绑定管理
- `llm_config.py` — LLM 配置 CRUD
- `prompt_template.py` — Prompt 模板 CRUD

### response_parser 包

`infrastructure/response_parser/` 是包（非单文件），对外导出 `MultiFormatResponseParser`：
- `__init__.py` — 按 `response_format` 分派到对应解析器
- `base.py` — `ParsedComment` 数据类 + `BaseParser` 抽象类
- `json_parser.py` — JSON 格式（支持 markdown 代码块包裹）
- `anthropic_parser.py` — Anthropic thinking 格式
- `xml_parser.py` — XML 格式
- `plain_text_parser.py` — 纯文本正则提取（always last in chain）

### 关键开发约定

- 所有数据库操作使用 SQLAlchemy async（`AsyncSession`、`async_sessionmaker`）
- `app.state` 在 FastAPI lifespan 中注入：`session_factory`、`orchestrator`、`config`、`notification_manager`、`engine`
- Service 层类在构造函数接收 `AsyncSession`，由 API 层管理 session 生命周期
- Celery 任务通过 `asyncio.run()` 包装异步代码；Worker 每任务创建独立 `session_factory`
- Webhook 签名验证：GitHub = HMAC-SHA256，GitLab = Token 直接比对，Gitee = SHA256 哈希
- `CommentAggregator` 合并行号间距 ≤5 的相邻同严重程度评论，超过 `max_comments_per_mr` 时按严重程度截断
- 代码使用 `match/case` 语法（Python 3.10+，项目目标 3.11+）
- 前端 API 模块命名：复数+驼峰（`projects.js`、`reviews.js`、`platforms.js`、`llmConfigs.js`、`templates.js`）

### 数据库迁移

`apps/backend/migrations/init.sql` 是唯一初始化脚本（含全部 10 张表和种子数据）。Docker 部署时挂载到 `docker-entrypoint-initdb.d/`，仅在空数据目录时执行，已有数据不受影响。
