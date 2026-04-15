# Code Review Service

基于 AI 的自动化代码评审服务，支持 GitHub、GitLab、Gitee 三大平台。

## 功能概览

- **多平台适配** — GitHub / GitLab / Gitee，统一接口，策略模式切换
- **Webhook 驱动** — 创建 MR/PR 或推送新 commit 时自动触发评审
- **AI 评审** — 通过 LiteLLM 统一接入 100+ 大模型（OpenAI / Anthropic / DeepSeek / 本地模型等）
- **数据库管理 Prompt 模板** — 按编程语言/语言标识分类，支持热更新，无需重启
- **评论聚合** — 相邻行号自动合并、严重程度分级、超阈值切换摘要模式
- **多项目支持** — 一套服务管理多个仓库，项目级独立配置
- **通知推送** — 飞书 / 钉钉 / 邮件，可配置启用
- **幂等 & 异步** — 事件去重、Celery 任务队列、评审状态追踪

---

## 技术栈

| 组件 | 选型 |
|------|------|
| Web 框架 | FastAPI |
| 数据库 | PostgreSQL + SQLAlchemy async |
| 任务队列 | Celery + Redis |
| LLM 接入 | LiteLLM |
| 依赖管理 | uv / hatch |
| 容器化 | Docker Compose |
| Python | >= 3.11 |

---

## 快速开始

### 方式一：Docker Compose（推荐）

```bash
# 1. 克隆项目
git clone <repo-url> && cd code-review

# 2. 复制并填写配置
cp configs/.env.example configs/.env
# 编辑 configs/.env，填入各平台的 Token 和 LLM API Key

# 3. 一键启动
cd docker && docker compose up -d

# 4. 验证服务
curl http://localhost:8000/api/v1/health
```

服务启动后：
- **API 服务**：`http://localhost:8000`
- **API 文档**：`http://localhost:8000/docs`（Swagger UI）
- **数据库**：`localhost:5432`
- **Redis**：`localhost:6379`

### 方式二：本地开发

**前置条件：** Python >= 3.11、PostgreSQL、Redis

```bash
# 1. 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 创建虚拟环境并安装依赖
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# 3. 初始化数据库
psql -U postgres -c "CREATE DATABASE code_review;"
psql -U postgres -d code_review -f configs/migrations/001_init.sql
psql -U postgres -d code_review -f configs/migrations/002_prompt_templates.sql

# 4. 复制配置
cp configs/.env.example .env
# 编辑 .env

# 5. 启动服务
uvicorn code_review.api.app:app --reload --port 8000

# 6. 另一个终端启动 Worker
celery -A code_review.worker worker -Q review -l info
```

---

## 项目结构

```
code-review/
├── src/code_review/
│   ├── core/                    # 统一接口定义（ABC）
│   │   ├── platform.py          #   PlatformAdapter — 平台适配接口
│   │   ├── llm.py               #   LLMReviewer — 大模型接口
│   │   └── notification.py      #   NotificationChannel — 通知接口
│   ├── adapters/                # 平台适配层（策略实现）
│   │   ├── github_adapter.py    #   GitHub（HMAC-SHA256 签名）
│   │   ├── gitlab_adapter.py    #   GitLab（Token 验证）
│   │   ├── gitee_adapter.py     #   Gitee
│   │   └── factory.py           #   适配器工厂
│   ├── infrastructure/          # 基础设施层
│   │   ├── llm_reviewer.py      #   LiteLLM 实现
│   │   ├── prompt_manager.py    #   数据库模板加载 + 热更新
│   │   ├── notification_*.py    #   飞书 / 钉钉 / 邮件
│   │   ├── celery_app.py        #   Celery 配置
│   │   └── cache.py             #   进程内 TTL 缓存（去重）
│   ├── services/                # 业务逻辑层
│   │   ├── review_orchestrator.py  # 评审编排器（核心流程）
│   │   ├── comment_aggregator.py   # 评论聚合策略
│   │   └── prompt_template_service.py # 模板 CRUD + 种子数据
│   ├── api/                     # API 层
│   │   ├── webhook.py           #   Webhook 接收端点
│   │   ├── management.py        #   项目管理 & 评审历史 API
│   │   ├── prompt_template.py   #   Prompt 模板 CRUD API
│   │   └── app.py               #   FastAPI 应用入口
│   ├── models/                  # 数据模型
│   │   ├── db.py                #   SQLAlchemy ORM
│   │   └── config.py            #   Pydantic 配置
│   └── worker.py                # Celery Worker 入口
├── configs/
│   ├── config.yaml              # 配置文件模板
│   ├── .env.example             # 环境变量模板
│   ├── migrations/              # SQL 迁移脚本
│   └── prompt_templates/        # 旧版文件模板（已废弃，保留供参考）
├── docker/
│   └── docker-compose.yml       # 四服务编排
├── tests/                       # 测试
├── Dockerfile
└── pyproject.toml
```

---

## 配置说明

支持三种配置方式（优先级从高到低）：

1. **环境变量** — 前缀 `CODE_REVIEW__`，双下划线分隔层级
2. **`.env` 文件** — 放在项目根目录
3. **YAML 配置文件** — `configs/config.yaml`

### 核心配置项

```yaml
# LLM — 通过 LiteLLM 支持 100+ 提供商
llm:
  model: "gpt-4"              # 或 deepseek/deepseek-chat, anthropic/claude-3-opus 等
  api_key: "sk-xxx"
  api_base: ""                 # 自部署模型填写 API 地址
  temperature: 0.3
  max_tokens: 4096

# 评审行为
review:
  comment_language: "zh"       # zh / en
  comment_mode: "detailed"     # detailed（行内评论）/ summary（仅摘要）
  max_comments_per_mr: 50
  exclude_patterns:            # 排除文件
    - "*.lock"
    - "vendor/**"
    - "node_modules/**"

# 通知
feishu:
  enabled: true
  webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
dingtalk:
  enabled: true
  webhook_url: "https://oapi.dingtalk.com/robot/send?access_token=xxx"
```

### 环境变量示例

```bash
# 所有敏感信息建议用环境变量
CODE_REVIEW__GITHUB__TOKEN=ghp_xxx
CODE_REVIEW__GITLAB__TOKEN=glpat-xxx
CODE_REVIEW__LLM__API_KEY=sk-xxx
CODE_REVIEW__LLM__MODEL=deepseek/deepseek-chat
CODE_REVIEW__DATABASE__URL=postgresql+asyncpg://user:pass@db:5432/code_review
```

---

## API 文档

服务启动后访问 `http://localhost:8000/docs` 查看完整的 Swagger UI。

### Webhook 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/webhook/github` | GitHub Webhook 接收 |
| POST | `/webhook/gitlab` | GitLab Webhook 接收 |
| POST | `/webhook/gitee` | Gitee Webhook 接收 |

### 项目管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/projects` | 创建项目 |
| GET | `/api/v1/projects` | 项目列表 |
| GET | `/api/v1/projects/{id}` | 项目详情 |
| PUT | `/api/v1/projects/{id}` | 更新项目 |
| DELETE | `/api/v1/projects/{id}` | 删除项目 |

### 评审历史

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/reviews` | 评审任务列表（支持 project_id/status 筛选） |
| GET | `/api/v1/reviews/{id}` | 评审任务详情 |
| GET | `/api/v1/reviews/{id}/comments` | 评审意见列表 |

### Prompt 模板管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/prompt-templates` | 创建模板 |
| GET | `/api/v1/prompt-templates` | 模板列表（支持 category/locale/enabled 筛选） |
| GET | `/api/v1/prompt-templates/search/by-name?name=xxx` | 按名称查询 |
| GET | `/api/v1/prompt-templates/{id}` | 按 ID 查询 |
| PUT | `/api/v1/prompt-templates/{id}` | 更新模板 |
| DELETE | `/api/v1/prompt-templates/{id}` | 删除模板 |

### 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/health` | 系统健康状态 |

---

## 使用流程

### 1. 注册项目

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-backend",
    "platform": "github",
    "platform_project_id": "myorg/my-backend",
    "webhook_secret": "your-webhook-secret"
  }'
```

### 2. 配置平台 Webhook

在 GitHub/GitLab/Gitee 仓库的 Settings → Webhooks 中添加：

| 平台 | Payload URL | Secret | 触发事件 |
|------|-------------|--------|----------|
| GitHub | `http://your-host/webhook/github` | 配置的 webhook_secret | Pull request events |
| GitLab | `http://your-host/webhook/gitlab` | 配置的 webhook_secret | Merge request events |
| Gitee | `http://your-host/webhook/gitee` | 配置的 webhook_secret | Pull Request |

### 3. 配置通知渠道

编辑 `.env` 或 `config.yaml`：

```bash
CODE_REVIEW__FEISHU__ENABLED=true
CODE_REVIEW__FEISHU__WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
```

### 4. 触发评审

开发者创建 MR/PR 或推送新 commit 时，自动触发评审流程：

```
Webhook → 签名验证 → 事件去重 → 获取变更 → 文件过滤
→ LLM 评审 → 评论聚合 → 发布行内评论 → 通知推送
```

### 5. 查看评审结果

```bash
# 查看某个项目的评审记录
curl http://localhost:8000/api/v1/reviews?project_id=<uuid>

# 查看评审详情和评论
curl http://localhost:8000/api/v1/reviews/<task_id>
curl http://localhost:8000/api/v1/reviews/<task_id>/comments
```

---

## Prompt 模板管理

模板存储在 PostgreSQL 的 `prompt_templates` 表中，支持热更新。

### 内置默认模板

服务首次启动时自动初始化以下模板：

| 名称 | 分类 | 语言 | 说明 |
|------|------|------|------|
| `default_zh` | default | zh | 通用中文评审模板 |
| `default_en` | default | en | 通用英文评审模板 |
| `python_zh` | python | zh | Python 专项中文模板 |
| `java_zh` | java | zh | Java 专项中文模板 |

### 模板匹配优先级

评审时按以下顺序查找模板：

1. **项目配置指定** — 项目 config 中的 `prompt_template_name`
2. **分类+语言精确匹配** — 如 `python` + `zh`
3. **分类匹配 + 任意语言** — 如 `python` + 任意
4. **默认分类+语言匹配** — `default` + `zh`
5. **默认分类+任意语言** — `default` + 任意
6. **代码内置兜底**

### 自定义模板示例

```bash
# 创建 Go 语言专项模板
curl -X POST http://localhost:8000/api/v1/prompt-templates \
  -H "Content-Type: application/json" \
  -d '{
    "name": "go_zh",
    "category": "go",
    "locale": "zh",
    "content": "请对以下 Go 代码变更进行专业评审...\n\n## 变更文件\n{{files_context}}\n\n## Diff\n```\n{{diff}}\n```"
  }'

# 指定项目使用特定模板
curl -X PUT http://localhost:8000/api/v1/projects/<project_id> \
  -H "Content-Type: application/json" \
  -d '{"config": {"prompt_template_name": "go_zh"}}'
```

### 热更新

修改数据库中的模板内容后，**下次评审自动生效**，无需重启服务。

---

## 评论聚合策略

| 策略 | 说明 |
|------|------|
| 相邻行合并 | 同文件、同 severity、行号间距 <= 5 行的评论自动合并 |
| 严重程度分级 | critical / warning / suggestion / info，带颜色标签 |
| 超阈值摘要 | 评论数超过 `severity_threshold_for_summary` 时切换为摘要模式 |
| 最大数量限制 | `max_comments_per_mr` 控制单次评审最多发布的评论数 |

---

## 项目级配置覆盖

创建项目时可通过 `config` 字段覆盖全局配置：

```json
{
  "name": "my-frontend",
  "platform": "github",
  "platform_project_id": "org/frontend",
  "config": {
    "prompt_template_name": "default_zh",
    "exclude_patterns": ["*.lock", "dist/**", "coverage/**"],
    "comment_mode": "summary"
  }
}
```

---

## 数据库表结构

| 表 | 说明 |
|----|------|
| `projects` | 项目配置（平台、仓库、Webhook 密钥、项目级配置） |
| `prompt_templates` | Prompt 模板（名称、内容、分类、语言、启用状态） |
| `review_tasks` | 评审任务（状态追踪：pending → in_progress → completed/failed） |
| `review_comments` | 评审意见（文件、行号、严重程度、建议） |

### 评审任务状态流转

```
pending → in_progress → completed
                    └──→ failed
```

---

## 测试

```bash
# 运行全部测试
pytest

# 带 coverage
pytest --cov=code_review --cov-report=html

# 运行指定测试
pytest tests/test_comment_aggregator.py -v
```

---

## 常见问题

### Q: 如何切换 LLM 模型？

修改配置中的 `llm.model` 和 `llm.api_key` 即可。LiteLLM 支持的模型前缀：

```bash
# OpenAI
CODE_REVIEW__LLM__MODEL=gpt-4o

# DeepSeek
CODE_REVIEW__LLM__MODEL=deepseek/deepseek-chat
CODE_REVIEW__LLM__API_BASE=https://api.deepseek.com

# Anthropic
CODE_REVIEW__LLM__MODEL=anthropic/claude-3-opus

# 本地部署（如 Ollama）
CODE_REVIEW__LLM__MODEL=ollama/codellama
CODE_REVIEW__LLM__API_BASE=http://localhost:11434
```

### Q: 如何添加新的编程语言模板？

通过 API 或直接操作数据库：

```bash
curl -X POST http://localhost:8000/api/v1/prompt-templates \
  -d '{"name": "rust_zh", "category": "rust", "locale": "zh", "content": "..."}'
```

系统会根据文件扩展名自动匹配 `category`（如 `.rs` → `rust`）。

### Q: 如何查看评审失败原因？

```bash
curl http://localhost:8000/api/v1/reviews?status=failed
curl http://localhost:8000/api/v1/reviews/<task_id>
# 查看 error_message 字段
```

### Q: Webhook 签名验证失败？

- GitHub：使用 `X-Hub-Signature-256` 头，HMAC-SHA256 签名
- GitLab：使用 `X-Gitlab-Token` 头，直接比对
- Gitee：SHA256 哈希验证

确保项目的 `webhook_secret` 与平台配置一致。

---

## License

MIT
