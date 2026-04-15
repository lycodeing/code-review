# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 构建与运行命令

```bash
# 安装依赖（需要 Python >= 3.11）
uv pip install -e ".[dev]"

# 启动 FastAPI 服务
uvicorn code_review.api.app:app --reload --port 8000

# 启动 Celery Worker（需要单独的终端）
celery -A code_review.worker worker -Q review -l info

# Docker Compose 部署（在 docker/ 目录下执行）
cd docker && docker compose up -d

# 运行全部测试
pytest

# 运行单个测试文件
pytest tests/test_comment_aggregator.py -v

# 运行单个测试函数
pytest tests/test_adapters.py::TestGitHubAdapter::test_parse_project_id -v

# 代码检查
ruff check src/ tests/

# 类型检查
mypy src/
```

## 架构概览

这是一个分层异步 Python 服务。评审流水线穿过四层：

```
core/（抽象接口）→ adapters/（平台实现）
                → infrastructure/（LLM、通知、缓存、Celery、加解密）
                → services/（业务逻辑 + 配置管理）
                → api/（FastAPI 路由）
```

### 核心数据流：Webhook → 评审完成

1. **API 层**（`api/webhook.py`）接收 POST 请求，通过平台适配器验证签名，解析为 `WebhookEvent`
2. **ReviewOrchestrator**（`services/review_orchestrator.py`）通过 `event_dedup_cache`（TTL 缓存）去重，在 PostgreSQL 创建 `ReviewTask` 记录，分发 Celery 任务
3. **Celery Worker**（`worker.py`）调用 `orchestrator.execute_review()`，流程为：
   - 从 DB `platform_configs` 表读取平台配置（token、api_url），空值降级到 env
   - 通过平台适配器获取 MR 变更文件
   - 按 `exclude_patterns` 过滤文件
   - 从 `prompt_templates` 数据库表加载 Prompt 模板（支持热更新）
   - 通过 LiteLLM（`infrastructure/llm_reviewer.py`）将 diff 发送给大模型
   - 聚合评论（相邻行合并、按严重程度排序、截断）
   - 向平台发布行内评论
   - 根据 `platform_notification_bindings` 查找该平台绑定的通知渠道，发送通知
   - 更新 `review_tasks` 状态：pending → in_progress → completed/failed

### 配置中心（数据库驱动）

平台和通知配置已从环境变量迁移到数据库管理，支持在线修改：

- **`platform_configs`** — 代码平台配置（gitee/github/gitlab），含 access_token、webhook_secret、api_url
- **`notification_configs`** — 通知渠道配置（dingtalk/feishu），含 webhook_url、secret、at_mobiles
- **`platform_notification_bindings`** — 多对多关联表，控制每个平台使用哪些通知渠道

**双读降级**：`PlatformConfigService.get_by_platform_with_fallback()` 优先读 DB，敏感字段为空时降级到 env 配置。Worker 端同样支持。

**加密**：敏感字段（access_token、webhook_secret、secret）写入 DB 时通过 `infrastructure/config_crypto.py` 使用 AES-256-GCM 加密，密钥从 `SERVER__SECRET_KEY` 派生。API 读取时返回 `********` 脱敏。

**REST API**：
- `/api/v1/platform-configs` — 平台配置 CRUD + 批量导入
- `/api/v1/notification-configs` — 通知渠道 CRUD + 批量导入 + 绑定管理（`PUT .../bindings`）

**不迁移的配置（保持环境变量）**：Server、Database、Redis、Celery、LLM、Review 行为参数。

### 环境变量配置

`AppConfig`（Pydantic Settings）加载优先级：环境变量（前缀 `CODE_REVIEW__`，双下划线分隔层级）> `.env` 文件 > 默认值。每个项目可通过 `projects.config` JSON 列覆盖全局配置（如 `prompt_template_name`、自定义 `exclude_patterns`）。

### 平台适配策略模式

`PlatformAdapter` ABC（`core/platform.py`）定义统一接口，`adapters/` 下的 `GitHubAdapter`、`GitLabAdapter`、`GiteeAdapter` 分别实现。`adapters/factory.py` 接收 `PlatformConfig` ORM 对象（从 DB 查询得到），不再依赖 `AppConfig`。所有适配器继承 `BasePlatformAdapter`，提供重试（tenacity）、自动分页、速率限制处理。

### Prompt 模板系统（数据库驱动）

模板存储在 PostgreSQL 的 `prompt_templates` 表中，不使用文件。`PromptTemplateManager`（`infrastructure/prompt_manager.py`）每次评审时实时查询数据库（天然支持热更新）。`PromptTemplateService`（`services/prompt_template_service.py`）处理 CRUD 和启动时的种子数据。匹配优先级：项目指定名称 > 分类+语言精确匹配 > 仅分类匹配 > default+语言 > default > 代码内置兜底。

### 关键开发约定

- 所有数据库操作使用 SQLAlchemy async（`AsyncSession`、`async_sessionmaker`）
- `app.state` 在 FastAPI lifespan 中注入共享对象：`session_factory`、`orchestrator`、`config`、`notification_manager`、`engine`
- API 路由通过 `request.app.state.session_factory` 获取数据库会话
- Service 层类（如 `PlatformConfigService`、`NotificationConfigService`、`PromptTemplateService`）在构造函数接收 `AsyncSession`，由 API 层负责创建 session 生命周期
- Webhook 签名验证因平台而异：GitHub = HMAC-SHA256，GitLab = Token 直接比对，Gitee = SHA256 哈希
- Celery 任务通过 `asyncio.run()` 包装异步代码——Celery 本身是同步的。Worker 每任务创建独立的 `session_factory`
- `CommentAggregator` 合并同严重程度、行号间距 <= 5 行的相邻评论，超过 `max_comments_per_mr` 时按严重程度优先级截断
- 代码使用 `match/case` 语法（需要 Python 3.10+，项目目标为 3.11+）
- 通知渠道类（`FeishuChannel`、`DingTalkChannel`）通过 `getattr` 接收 ORM 对象或兼容对象，不依赖特定的 Pydantic config 类
