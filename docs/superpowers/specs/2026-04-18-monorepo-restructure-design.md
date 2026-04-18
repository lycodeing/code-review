# 设计规范：Monorepo 结构重组与代码分层改造

**日期**：2026-04-18  
**状态**：已批准  
**范围**：项目目录结构重组、后端超大文件拆分、前端目录规范、开发规范文档

---

## 一、背景与问题诊断

### 1.1 当前结构痛点

| 问题 | 具体表现 | 影响 |
|------|----------|------|
| 前后端混杂于根目录 | `src/`（后端）与 `frontend/`（前端）并列，后端配置文件（`pyproject.toml`、`Dockerfile`）散落根目录 | 新人理解成本高，CI/CD 路径混乱 |
| 迁移脚本分散两处 | `configs/migrations/`（5个文件）与 `migrations/`（1个文件）独立存在 | 执行顺序不明确，容易遗漏 |
| 超大文件违反单一职责 | `management.py`（473行）混合项目/评审/配置逻辑；`response_parser.py`（744行）处理4种格式 | 可读性差，测试粒度粗，改动影响面大 |
| 前端 API 模块命名不统一 | `project.js` vs `llm.js`，单复数混用，语义模糊 | 协作时查找困难 |

### 1.2 代码规模基线

- 后端 Python：45个文件，7880行
- 前端 Vue/JS：40个文件，~5000行
- 测试：9个文件，1200行
- 数据库表：10个
- API 端点：40+个

---

## 二、设计目标

1. **前后端彻底分离**：monorepo 顶层只做编排，业务代码归入 `apps/backend/` 和 `apps/frontend/`
2. **单一职责**：每个文件只负责一个明确的资源或解析格式
3. **代码层级友好**：目录即文档，层级名称直接表达职责
4. **开发规范落地**：前后端各有明确的分层契约，写入规范文档

---

## 三、目标目录结构

### 3.1 顶层 Monorepo 结构

```
code-review/
├── apps/
│   ├── backend/                        ← Python 后端（完整独立）
│   │   ├── src/
│   │   │   └── code_review/            ← 源代码包
│   │   │       ├── api/                ← FastAPI 路由层
│   │   │       ├── core/               ← 抽象接口（ABC）
│   │   │       ├── adapters/           ← 平台适配层（策略模式）
│   │   │       ├── infrastructure/     ← 基础设施层
│   │   │       ├── services/           ← 业务逻辑层
│   │   │       ├── models/             ← ORM 模型 + Pydantic 配置
│   │   │       ├── schemas/            ← API 请求/响应 Schema
│   │   │       └── worker.py           ← Celery 任务入口
│   │   ├── tests/                      ← 后端测试（从根目录迁移）
│   │   ├── migrations/                 ← 合并后的迁移脚本（001~006）
│   │   ├── configs/                    ← config.yaml + .env.example
│   │   ├── Dockerfile                  ← 从根目录迁移
│   │   └── pyproject.toml              ← 从根目录迁移
│   └── frontend/                       ← Vue 3 前端（从根目录迁移）
│       ├── src/
│       ├── package.json
│       ├── vite.config.js
│       └── index.html
├── docker/
│   └── docker-compose.yml              ← 构建路径更新为 ./apps/backend/Dockerfile
└── README.md
```

**根目录移除内容**：`src/`、`tests/`、`configs/`、`migrations/`、`Dockerfile`、`pyproject.toml`、`uv.lock`、`frontend/`

### 3.2 后端 API 层（拆分后）

```
apps/backend/src/code_review/api/
├── app.py                ← FastAPI 应用入口 + lifespan（199行，不变）
├── webhook.py            ← Webhook 接收端点（153行，不变）
├── projects.py           ← 项目 CRUD + 评审历史（从 management.py 拆出）
├── reviews.py            ← 评审列表/详情（从 management.py 拆出）
├── platform_config.py    ← 平台配置 CRUD（不变）
├── notification_config.py← 通知配置 CRUD（不变）
├── llm_config.py         ← LLM 配置 CRUD（不变）
└── prompt_template.py    ← Prompt 模板 CRUD（不变）
```

**原 `management.py` 拆分规则**：
- `router = APIRouter(prefix="/api/v1/projects")` → `projects.py`
- `router = APIRouter(prefix="/api/v1/reviews")` → `reviews.py`
- `app.py` 中的 `include_router` 调用相应更新

### 3.3 基础设施层（响应解析器拆分后）

```
apps/backend/src/code_review/infrastructure/
├── response_parser/
│   ├── __init__.py         ← 对外导出 ResponseParser（调用方零改动）
│   ├── base.py             ← ParsedComment 数据类 + BaseParser 抽象类
│   ├── json_parser.py      ← JSON 格式解析（~150行）
│   ├── anthropic_parser.py ← Anthropic thinking 格式（~150行）
│   ├── xml_parser.py       ← XML 格式解析（~120行）
│   └── plain_text_parser.py← 纯文本正则提取（~100行）
├── llm_reviewer.py         ← 不变
├── langchain_reviewer.py   ← 不变
├── prompt_manager.py       ← 不变
├── notification_manager.py ← 不变
├── notification_feishu.py  ← 不变
├── notification_dingtalk.py← 不变
├── notification_email.py   ← 不变
├── config_crypto.py        ← 不变
├── cache.py                ← 不变
└── celery_app.py           ← 不变
```

**`__init__.py` 导出契约**（保持调用方不变）：
```python
from .json_parser import JsonParser
from .anthropic_parser import AnthropicParser
from .xml_parser import XmlParser
from .plain_text_parser import PlainTextParser
from .base import ParsedComment

class ResponseParser:
    """根据 response_format 分派到对应解析器"""
    ...
```

### 3.4 迁移脚本合并

```
apps/backend/migrations/
├── 001_init.sql                          ← 原 configs/migrations/001_init.sql
├── 002_prompt_templates.sql              ← 原 configs/migrations/002_prompt_templates.sql
├── 003_platform_and_notification.sql     ← 原 configs/migrations/003_*
├── 004_add_response_format.sql           ← 原 configs/migrations/004_*
├── 005_add_project_prompt_bindings.sql   ← 原 configs/migrations/005_*
└── 006_add_llm_configs.sql               ← 原 migrations/002_add_llm_configs.sql（重编号）
```

### 3.5 前端目录规范

```
apps/frontend/src/
├── api/              ← HTTP 请求层（只做数据获取，不含业务逻辑）
│   ├── index.js      ← axios 实例 + 请求/响应拦截器
│   ├── auth.js
│   ├── projects.js   ← 复数命名（原 project.js）
│   ├── reviews.js    ← 复数命名（原 review.js）
│   ├── platforms.js  ← 复数命名（原 platform.js）
│   ├── notifications.js
│   ├── llmConfigs.js ← 驼峰命名，语义明确（原 llm.js）
│   └── templates.js  ← 复数命名（原 template.js）
├── views/            ← 页面组件（页面编排，调用 store/composable）
├── components/       ← 可复用展示组件（props/emit 通信）
├── stores/           ← Pinia 状态管理（状态 + 调用 api 层）
├── router/           ← 路由配置 + 导航守卫
├── composables/      ← 跨视图复用的状态逻辑
└── utils/            ← 纯工具函数（无副作用）
```

---

## 四、开发规范

### 4.1 后端分层契约

| 层级 | 职责 | 依赖方向 | 禁止 |
|------|------|----------|------|
| `api/` | 接收 HTTP 请求，参数校验，调用 service，返回响应 | → service | 不含业务逻辑，不直接操作 DB |
| `services/` | 业务流程编排，事务边界，调用 infrastructure/adapters | → infrastructure, adapters | 不含 HTTP 细节（状态码、Header） |
| `infrastructure/` | 外部系统集成（LLM、通知、缓存、加密） | → core（接口） | 不含业务规则 |
| `adapters/` | 平台 API 封装，实现 core 接口 | → core | 不含业务逻辑 |
| `core/` | 抽象接口定义（ABC） | 无外部依赖 | 不含实现代码 |
| `models/` | ORM 模型 + Pydantic 配置模型 | → 数据库 | 不含业务方法 |
| `schemas/` | API 请求/响应 Schema | 无外部依赖 | 不含 ORM 模型引用 |

### 4.2 前端分层契约

| 层级 | 职责 | 禁止 |
|------|------|------|
| `api/*.js` | 只做 HTTP 请求，返回原始响应数据 | 不含 UI 逻辑，不调用 store，不处理错误 UI |
| `stores/*.js` | 状态持久化，调用 api 层，处理异步 | 不直接操作 DOM，不含路由跳转 |
| `views/*.vue` | 页面编排，调用 store 或 composable | 不直接调用 api 层，不含复杂计算逻辑 |
| `components/*.vue` | 纯展示组件，通过 props/emit 通信 | 不含业务逻辑，不调用 store |
| `composables/*.js` | 跨视图复用的响应式逻辑 | 不含 UI 样式逻辑 |
| `utils/*.js` | 纯函数，数据转换、格式化 | 无副作用，不依赖 Vue 响应式 |

### 4.3 文件命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 后端 Python 文件 | `snake_case.py` | `review_orchestrator.py` |
| 前端 Vue 组件 | `PascalCase.vue` | `ReviewList.vue` |
| 前端 JS 模块 | `camelCase.js` 或 `kebab-case.js` | `llmConfigs.js` |
| 前端 store | `camelCase.js`，文件名即 store 名 | `user.js` |
| 数据库迁移 | `NNN_snake_case.sql`（3位编号） | `006_add_llm_configs.sql` |

### 4.4 不在本次改造范围内

- 前端 TypeScript 迁移
- 后端业务逻辑重构（services/ 层内部）
- 新增功能特性
- 测试覆盖率提升

---

## 五、改造步骤规划

改造分 4 个阶段，每阶段独立可验证：

### 阶段 1：目录骨架搭建（不移动代码）
1. 创建 `apps/backend/` 和 `apps/frontend/` 目录结构
2. 验证：目录结构符合设计

### 阶段 2：文件迁移（不修改代码内容）
1. 后端代码：`src/` → `apps/backend/src/`
2. 后端测试：`tests/` → `apps/backend/tests/`
3. 后端配置：`configs/` → `apps/backend/configs/`
4. 后端构建：`Dockerfile` + `pyproject.toml` + `uv.lock` → `apps/backend/`
5. 迁移脚本合并：两处 migrations → `apps/backend/migrations/`（重编号 006）
6. 前端代码：`frontend/` → `apps/frontend/`
7. 验证：`cd apps/backend && python -m pytest` 全部通过

### 阶段 3：后端代码拆分
1. 拆分 `management.py` → `projects.py` + `reviews.py`
2. 更新 `app.py` 的 `include_router` 引用
3. 拆分 `response_parser.py` → `response_parser/` 包（4个解析器 + `__init__.py`）
4. 验证：`pytest` 全部通过，`ruff check` 无报错

### 阶段 4：前端 API 模块重命名
1. `project.js` → `projects.js`，`review.js` → `reviews.js`，`platform.js` → `platforms.js`，`llm.js` → `llmConfigs.js`，`template.js` → `templates.js`
2. 更新所有 import 引用
3. 更新 `docker-compose.yml` 构建路径
4. 验证：前端 `npm run build` 无报错，服务正常启动

---

## 六、风险与缓解

| 风险 | 概率 | 缓解措施 |
|------|------|----------|
| Python 包路径变更导致 import 失败 | 中 | 阶段2完成后立即运行 pytest，`pyproject.toml` 中的 `packages` 配置跟随更新 |
| docker-compose 构建路径失效 | 低 | 阶段4统一更新，构建前验证 |
| 前端 import 引用遗漏 | 低 | 使用 `grep -r "from.*llm\|import.*llm"` 全量检查后重命名 |
| response_parser 拆分后接口不兼容 | 中 | `__init__.py` 保持原有 `ResponseParser` 类导出，调用方零改动 |

---

## 七、验收标准

- [ ] `apps/backend/` 和 `apps/frontend/` 目录存在，根目录无业务代码
- [ ] `apps/backend/migrations/` 有且仅有 001~006 共6个文件
- [ ] `apps/backend/src/code_review/api/` 无 `management.py`，有 `projects.py` 和 `reviews.py`
- [ ] `apps/backend/src/code_review/infrastructure/response_parser/` 是目录（包），有5个文件
- [ ] `apps/frontend/src/api/` 文件名全部为复数或驼峰命名，无 `project.js`/`review.js`/`llm.js`
- [ ] `pytest`（后端）全部通过
- [ ] `ruff check`（后端）无报错
- [ ] `npm run build`（前端）无报错
- [ ] `docker compose up` 服务正常启动
