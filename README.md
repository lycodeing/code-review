# Code Review Service

基于 AI 的自动化代码评审服务，支持 GitHub、GitLab、Gitee 三大平台，提供 Vue 3 管理界面。

## 功能概览

- **多平台适配** — GitHub / GitLab / Gitee，统一接口，策略模式切换
- **Webhook 驱动** — 创建 MR/PR 或推送新 commit 时自动触发评审
- **AI 评审** — 通过 LiteLLM 统一接入 100+ 大模型（OpenAI / Anthropic / DeepSeek / 本地模型等）
- **配置中心** — 平台配置、通知渠道、LLM 配置均支持数据库管理 + 在线修改
- **Prompt 模板管理** — 按编程语言/语言标识分类，支持热更新，无需重启
- **评论聚合** — 相邻行号自动合并、严重程度分级、超阈值截断
- **多项目支持** — 一套服务管理多个仓库，项目级独立配置
- **通知推送** — 飞书 / 钉钉 / 邮件，按平台绑定独立渠道
- **幂等 & 异步** — Redis 事件去重、Celery 任务队列、评审状态追踪
- **管理界面** — Vue 3 前端，可视化管理所有配置和评审记录

---

## 技术栈

| 组件 | 选型 |
|------|------|
| Web 框架 | FastAPI + Uvicorn |
| 数据库 | PostgreSQL 16 + SQLAlchemy async |
| 任务队列 | Celery + Redis |
| LLM 接入 | LiteLLM / LangChain |
| 前端 | Vue 3 + Vite + Element Plus + Pinia |
| 依赖管理 | uv + hatchling |
| 容器化 | Docker Compose |
| Python | >= 3.11 |

---

## 项目结构

```
code-review/                        ← Monorepo 根目录
├── apps/
│   ├── backend/                    ← Python 后端
│   │   ├── src/code_review/
│   │   │   ├── api/                ← FastAPI 路由层
│   │   │   ├── services/           ← 业务逻辑层
│   │   │   ├── infrastructure/     ← LLM · 通知 · 缓存 · 加密
│   │   │   ├── adapters/           ← GitHub / GitLab / Gitee 适配器
│   │   │   ├── core/               ← 抽象接口（ABC）
│   │   │   ├── models/             ← ORM + Pydantic 配置
│   │   │   ├── schemas/            ← API Schema
│   │   │   └── worker.py           ← Celery 任务入口
│   │   ├── migrations/
│   │   │   └── init.sql            ← 数据库初始化（10 张表）
│   │   ├── configs/
│   │   │   └── .env.example        ← 环境变量模板
│   │   ├── tests/                  ← 后端测试
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   └── frontend/                   ← Vue 3 前端
│       └── src/
│           ├── api/                ← Axios HTTP 客户端
│           ├── views/              ← 页面组件
│           ├── stores/             ← Pinia 状态管理
│           ├── components/         ← 可复用组件
│           └── router/             ← 路由配置
└── docker/
    └── docker-compose.yml          ← 四服务编排
```

---

## 快速开始

### 方式一：Docker Compose（推荐）

```bash
# 1. 克隆项目
git clone <repo-url> && cd code-review

# 2. 复制并填写配置
cp apps/backend/configs/.env.example apps/backend/configs/.env
# 编辑 .env，至少填写 SERVER__SECRET_KEY 和 LLM 配置

# 3. 启动所有服务
cd docker && docker compose up -d

# 4. 验证服务
curl http://localhost:8000/api/v1/health
```

服务启动后：
- **后端 API**：`http://localhost:8000`
- **Swagger 文档**：`http://localhost:8000/docs`
- **数据库**：`localhost:5432`
- **Redis**：`localhost:6380`

### 方式二：本地开发

**前置条件：** Python >= 3.11、PostgreSQL、Redis、Node.js >= 18

```bash
# 后端
cd apps/backend
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# 初始化数据库
psql -U postgres -c "CREATE DATABASE code_review;"
psql -U postgres -d code_review -f migrations/init.sql

# 复制配置
cp configs/.env.example configs/.env  # 编辑填写

# 启动后端
uvicorn code_review.api.app:app --reload --port 8000

# 另一个终端启动 Worker
celery -A code_review.worker worker -Q review -l info

# 前端（另一个终端）
cd apps/frontend
npm install
npm run dev  # http://localhost:3000
```

---

## 配置说明

所有配置通过环境变量注入，前缀 `CODE_REVIEW__`，双下划线分隔层级：

```bash
# 必填：服务密钥（用于 AES-256-GCM 加密敏感字段）
CODE_REVIEW__SERVER__SECRET_KEY=your-secret-key-min-32-chars

# 数据库
CODE_REVIEW__DATABASE__URL=postgresql+asyncpg://postgres:postgres@localhost:5432/code_review

# Redis
CODE_REVIEW__REDIS__URL=redis://localhost:6379/0

# LLM（通过 LiteLLM 支持 100+ 模型）
CODE_REVIEW__LLM__MODEL=deepseek/deepseek-chat
CODE_REVIEW__LLM__API_KEY=sk-xxx
CODE_REVIEW__LLM__API_BASE=https://api.deepseek.com
```

平台配置、通知渠道、LLM 配置均可通过管理界面或 API 在数据库中管理，无需修改配置文件。

---

## API 端点

| 资源 | 路径前缀 | 说明 |
|------|---------|------|
| Webhook | `/webhook/{platform}` | 接收 GitHub / GitLab / Gitee 事件 |
| 项目 | `/api/v1/projects` | 项目 CRUD + LLM 绑定 |
| 评审 | `/api/v1/reviews` | 评审列表 / 详情 / 手动触发 |
| 平台配置 | `/api/v1/platform-configs` | 平台 Token / Webhook 密钥管理 |
| 通知配置 | `/api/v1/notification-configs` | 飞书 / 钉钉 / 邮件配置 + 绑定管理 |
| LLM 配置 | `/api/v1/llm-configs` | 多 LLM 提供商配置 |
| Prompt 模板 | `/api/v1/prompt-templates` | 模板 CRUD（支持热更新） |
| 健康检查 | `/api/v1/health` | 服务状态 |

---

## 数据库表

| 表 | 说明 |
|----|------|
| `projects` | 项目配置 |
| `review_tasks` | 评审任务（pending → in_progress → completed/failed） |
| `review_comments` | 评审意见 |
| `prompt_templates` | Prompt 模板 |
| `platform_configs` | 代码平台配置（加密存储） |
| `notification_configs` | 通知渠道配置（加密存储） |
| `llm_configs` | LLM 提供商配置（加密存储） |
| `platform_notification_bindings` | 平台-通知渠道关联 |
| `project_prompt_bindings` | 项目-模板关联 |
| `project_llm_bindings` | 项目-LLM 配置关联 |

---

## 测试

```bash
cd apps/backend

# 运行全部测试
pytest

# 带覆盖率
pytest --cov=code_review --cov-report=html

# 代码检查
ruff check src/ tests/
```

---

## 架构文档

详见 [docs/architecture.md](docs/architecture.md)，包含：

- 系统架构图（分层组件关系）
- 端到端时序图（Webhook → 评审完成）
- 数据模型关系图（10 张表）
- Prompt 模板匹配优先级流程图
- 部署架构图

---

## License

MIT
