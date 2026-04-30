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
# 增量迁移按顺序执行
psql -U postgres -d code_review -f apps/backend/migrations/add_notification_templates.sql
psql -U postgres -d code_review -f apps/backend/migrations/add_api_call_logs.sql
psql -U postgres -d code_review -f apps/backend/migrations/add_dashboard_index.sql
psql -U postgres -d code_review -f apps/backend/migrations/add_notification_extra_config.sql
psql -U postgres -d code_review -f apps/backend/migrations/add_review_rules.sql
psql -U postgres -d code_review -f apps/backend/migrations/add_comment_replies.sql
psql -U postgres -d code_review -f apps/backend/migrations/add_system_settings.sql

# 运行全部测试
cd apps/backend && pytest

# 运行单个测试文件
cd apps/backend && pytest tests/test_comment_aggregator.py -v

# 运行单个测试函数
cd apps/backend && pytest tests/test_adapters.py::TestGitHubAdapter::test_parse_project_id -v

# 带覆盖率
cd apps/backend && pytest --cov=code_review --cov-report=html

# 代码检查
cd apps/backend && ruff check src/ tests/

# 类型检查（strict 模式）
cd apps/backend && mypy src/
```

## 架构概览

Monorepo 结构：`apps/backend/`（Python FastAPI）+ `apps/frontend/`（Vue 3 + Element Plus + Pinia）+ `docker/`（编排）。

评审流水线穿过四层：

```
core/（抽象接口 ABC + 错误定义）
  → adapters/（GitHub / GitLab / Gitee 平台实现）
  → infrastructure/（LangChain LLM、通知、缓存、Celery、加解密、response_parser）
  → services/（业务逻辑 + 配置管理 + 规则引擎）
  → api/（FastAPI 路由）
```

### 核心数据流：Webhook → 评审完成

1. **API 层**（`api/webhook.py`）接收 POST 请求，通过平台适配器验证签名，解析为 `WebhookEvent`
2. **ReviewOrchestrator**（`services/review_orchestrator.py`）通过 TTL 缓存去重，在 PostgreSQL 创建 `ReviewTask`，分发 Celery 任务
3. **Celery Worker**（`worker.py`）调用 `orchestrator.execute_review()`，流程：
   - 读取 `platform_configs` 表获取平台配置（token、api_url），空值降级到 env
   - 通过平台适配器获取 MR 变更文件，按 `exclude_patterns` 过滤
   - **规则引擎**（`services/rule_engine.py`）执行确定性正则规则检查（按项目绑定的规则匹配 diff）
   - 从 `prompt_templates` 表加载 Prompt 模板（热更新，每次评审实时查询）
   - 通过 LangChain（`infrastructure/langchain_reviewer.py`）调用大模型
   - 聚合评论、发布行内评论、发送通知
   - 记录 API 调用日志到 `api_call_logs` 表
   - 更新任务状态：pending → in_progress → completed/failed

### 双层评审：规则引擎 + LLM

评审由两个独立层组成，规则引擎先于 LLM 执行：
- **确定性规则**（`services/rule_engine.py`）：基于正则表达式，按文件 glob 模式过滤，命中后生成指定严重程度的评论
- **LLM 评审**（`infrastructure/langchain_reviewer.py`）：通过 LangChain 调用大模型，支持多格式响应解析

### 评论回复（多轮对话）

`api/comment_replies.py` 支持评审评论的多轮对话：
- 用户回复评论，LLM 可基于对话历史自动生成回复（`POST /{comment_id}/replies/llm-respond`）
- 回复来源通过 `source` 字段区分：`user` / `llm` / `system`
- 支持嵌套回复（`parent_reply_id`）

### 配置中心（数据库驱动）

- **`platform_configs`** — 代码平台配置（gitee/github/gitlab），含 access_token、webhook_secret、api_url
- **`notification_configs`** — 通知渠道配置（dingtalk/feishu/email），含 webhook_url、secret、at_mobiles、extra_config
- **`llm_configs`** — LLM 提供商配置，含 model_name、api_key、api_base、response_format（auto/json/anthropic_thinking/xml/plain_text）
- **`notification_templates`** — 通知消息模板，支持 Jinja2 变量，按渠道（dingtalk/feishu）分类
- **`review_rules`** — 评审规则定义（regex 类型），含 pattern、severity、file_pattern
- **`platform_notification_bindings`** — 平台-通知渠道多对多关联
- **`project_llm_bindings`** / **`project_prompt_bindings`** / **`project_rule_bindings`** — 项目级资源配置关联（多对多，含优先级和默认标记）
- **`project_notification_template_bindings`** — 项目级通知模板绑定

敏感字段（token、key、secret）通过 `infrastructure/config_crypto.py` 使用 AES-256-GCM 加密，密钥从 `CODE_REVIEW__SERVER__SECRET_KEY` 派生。`PlatformConfigService.get_by_platform_with_fallback()` 优先读 DB，敏感字段为空时降级到 env。

不迁移到 DB 的配置（保持环境变量）：Server、Database、Redis、Celery、Review 行为参数。

### API 路由文件

`apps/backend/src/code_review/api/` 各文件对应独立资源：
- `webhook.py` — Webhook 接收端点（签名验证 + 任务分发）
- `projects.py` — 项目 CRUD + 评审历史 + LLM/Prompt/Rule 绑定
- `reviews.py` — 评审列表 / 详情 / 手动触发
- `dashboard.py` — 仪表盘统计（周期统计、趋势图、严重程度分布、项目排行）
- `comment_replies.py` — 评论回复 CRUD + LLM 自动回复
- `review_rules.py` — 评审规则 CRUD + 项目绑定
- `platform_config.py` — 平台配置 CRUD
- `notification_config.py` — 通知配置 CRUD + 绑定管理
- `notification_template.py` — 通知模板 CRUD + 渠道模板 + 项目绑定
- `llm_config.py` — LLM 配置 CRUD + 项目绑定
- `prompt_template.py` — Prompt 模板 CRUD + 项目绑定
- `logs.py` — API 调用日志查看
- `system_settings.py` — 系统配置（通用 key-value 模式，支持 number/switch/text/select 输入类型）读写 + 分类列表

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
- LLM 集成通过 LangChain（`langchain-openai` / `langchain-community`），非 LiteLLM
- `RetryableError`（`core/errors.py`）标识可重试的瞬态故障（LLM 超时、网络错误、限流）
- 前端 API 模块命名：复数+驼峰（`projects.js`、`reviews.js`、`platforms.js`、`llmConfigs.js`、`templates.js`）
- 结构化日志使用 structlog（JSON 格式输出）
- **新增前端页面必须同步三处**：① `apps/frontend/src/router/routes.js` 添加路由 ② `apps/frontend/src/components/layout/Sidebar.vue` 添加菜单项并导入图标 ③ 菜单项名称不能与父级子菜单名称重复。完成后必须 `npm run build` 验证，Docker 部署需 `docker compose up -d --build frontend` 重建容器

### 数据库模型

ORM 模型定义在 `models/db.py`，当前共 16 张表：
- 核心业务：`projects`、`review_tasks`、`review_comments`、`comment_replies`
- 模板管理：`prompt_templates`、`notification_templates`
- 配置管理：`platform_configs`、`notification_configs`、`llm_configs`、`review_rules`
- 系统配置：`system_settings`（key-value 模式，存储超时等系统级动态配置）
- 关联绑定：`platform_notification_bindings`、`project_llm_bindings`、`project_prompt_bindings`、`project_rule_bindings`、`project_notification_template_bindings`
- 日志：`api_call_logs`（记录 LLM 调用和通知发送的请求/响应详情）

所有表使用 UUID 主键，`created_at`/`updated_at` 统一用 UTC 时区。

### 数据库迁移

`apps/backend/migrations/init.sql` 是初始化脚本（含基础表和种子数据）。后续增量迁移需按顺序执行：
1. `add_notification_templates.sql`
2. `add_api_call_logs.sql`
3. `add_dashboard_index.sql`
4. `add_notification_extra_config.sql`
5. `add_review_rules.sql`
6. `add_comment_replies.sql`
7. `add_system_settings.sql`

Docker 部署时 `init.sql` 挂载到 `docker-entrypoint-initdb.d/`，仅在空数据目录时执行，已有数据不受影响。应用启动时 `Base.metadata.create_all` 会自动创建缺失的表结构。

### 工具链配置

- **Ruff**：target py311，line-length 100，lint 规则 E/F/I/N/W/UP
- **mypy**：strict 模式，python_version 3.11
- **pytest**：asyncio_mode=auto，pythonpath=src
- **构建系统**：hatchling
