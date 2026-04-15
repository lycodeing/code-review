# 配置中心改造方案

> 将代码平台（Gitee/GitHub/GitLab）和通知渠道（钉钉/飞书）配置从环境变量迁移到数据库统一管理。

---

## 一、数据库表设计

### 1.1 代码平台配置表 `platform_configs`

每个平台一行记录，字段直接对应平台连接参数。

```sql
CREATE TABLE platform_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform        VARCHAR(32)  NOT NULL,    -- github | gitlab | gitee
    access_token    TEXT         NOT NULL DEFAULT '',  -- API 访问令牌（加密存储）
    webhook_secret  TEXT         NOT NULL DEFAULT '',  -- Webhook 签名密钥（加密存储）
    api_url         VARCHAR(512) NOT NULL DEFAULT '',  -- API 基础地址
    enabled         BOOLEAN      NOT NULL DEFAULT TRUE,
    description     VARCHAR(512) NOT NULL DEFAULT '',
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP    NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_platform UNIQUE (platform)
);

-- 初始数据
INSERT INTO platform_configs (platform, access_token, webhook_secret, api_url, enabled, description) VALUES
    ('gitee',  '', '', 'https://gitee.com/api/v5',      true, 'Gitee 代码平台'),
    ('github', '', '', 'https://api.github.com',          true, 'GitHub 代码平台'),
    ('gitlab', '', '', 'https://gitlab.com/api/v4',      true, 'GitLab 代码平台')
ON CONFLICT (platform) DO NOTHING;
```

**字段说明：**

| 字段 | 类型 | 说明 | 加密 | 默认值 |
|------|------|------|------|--------|
| platform | varchar(32) | 平台标识，唯一约束 | 否 | — |
| access_token | text | API 访问令牌 | 是 | '' |
| webhook_secret | text | Webhook 签名密钥 | 是 | '' |
| api_url | varchar(512) | API 基础地址 | 否 | 各平台默认地址 |
| enabled | boolean | 是否启用该平台 | 否 | true |
| description | varchar(512) | 说明文字 | 否 | '' |

### 1.2 通知渠道配置表 `notification_configs`

每个渠道一行记录，字段对应通知参数。

```sql
CREATE TABLE notification_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel         VARCHAR(32)  NOT NULL,    -- dingtalk | feishu | email
    enabled         BOOLEAN      NOT NULL DEFAULT FALSE,
    webhook_url     VARCHAR(1024) NOT NULL DEFAULT '',
    secret          TEXT         NOT NULL DEFAULT '',   -- 签名密钥（加密存储）
    at_mobiles      VARCHAR(1024) NOT NULL DEFAULT '', -- @指定人（逗号分隔手机号）
    description     VARCHAR(512) NOT NULL DEFAULT '',
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP    NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_notification_channel UNIQUE (channel)
);

-- 初始数据
INSERT INTO notification_configs (channel, enabled, webhook_url, secret, description) VALUES
    ('dingtalk', false, '', '', '钉钉机器人通知'),
    ('feishu',   false, '', '', '飞书机器人通知')
ON CONFLICT (channel) DO NOTHING;
```

**字段说明：**

| 字段 | 类型 | 适用渠道 | 说明 | 加密 |
|------|------|---------|------|------|
| channel | varchar(32) | 全部 | 渠道标识，唯一约束 | 否 |
| enabled | boolean | 全部 | 是否启用 | 否 |
| webhook_url | varchar(1024) | 钉钉、飞书 | 机器人 Webhook 地址 | 否 |
| secret | text | 钉钉、飞书 | 签名验证密钥 | 是 |
| at_mobiles | varchar(1024) | 钉钉 | @人手机号列表（逗号分隔） | 否 |
| description | varchar(512) | 全部 | 说明文字 | 否 |

### 1.3 平台-通知关联表 `platform_notification_bindings`

多对多关联：一个平台可绑定多个通知渠道，一个通知渠道可服务多个平台。

```sql
CREATE TABLE platform_notification_bindings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id     UUID NOT NULL REFERENCES platform_configs(id) ON DELETE CASCADE,
    notification_id UUID NOT NULL REFERENCES notification_configs(id) ON DELETE CASCADE,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_platform_notification UNIQUE (platform_id, notification_id)
);

-- 默认绑定：所有平台关联所有通知渠道
INSERT INTO platform_notification_bindings (platform_id, notification_id, enabled)
SELECT p.id, n.id, true
FROM platform_configs p
CROSS JOIN notification_configs n
ON CONFLICT (platform_id, notification_id) DO NOTHING;
```

**业务语义：** 当平台（如 Gitee）的评审完成后，系统根据 `platform_notification_bindings` 查找该平台绑定的通知渠道，仅向绑定的渠道发送通知。

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| platform_id | UUID | 关联 platform_configs.id，级联删除 |
| notification_id | UUID | 关联 notification_configs.id，级联删除 |
| enabled | boolean | 绑定是否启用（独立于渠道自身的 enabled） |

### 1.4 设计对比

| 对比项 | 单表 system_configs | 双表 platform_configs + notification_configs |
|--------|-------------------|----------------------------------------------|
| 查询方式 | 需要 WHERE category='platform' AND name='gitee' | 直接 WHERE platform='gitee' |
| 字段约束 | 所有值都是 TEXT，无法校验 URL 格式 | api_url / webhook_url 可做类型校验 |
| 敏感标记 | 需要 encrypted 布尔字段 | 哪些字段加密在代码层面固定，无需存储 |
| JOIN 成本 | 消费层需要多次查询拼装 | 一次查询获取完整配置 |
| 扩展性 | 加新字段只需加行 | 加新字段需 ALTER TABLE |
| 可读性 | EAV 键值对，需理解 category/name/key 含义 | 一行即一个平台的完整配置，直观 |

**选择双表方案的原因：**
1. 两个业务域字段差异大（平台有 api_url/access_token，渠道有 webhook_url/secret/at_mobiles）
2. 查询模式不同：平台配置按 platform 查，通知配置按 channel 查
3. 各表字段语义明确，不需要 category/key 两级定位
4. ORM 模型直接映射，代码清晰

### 1.4 加密策略

敏感字段（`access_token`、`webhook_secret`、`secret`）在写入 DB 时使用 AES-256-GCM 加密：

| 要素 | 来源 |
|------|------|
| 加密密钥 | 从 `CODE_REVIEW__SERVER__SECRET_KEY` 派生（PBKDF2，固定 salt） |
| 加密算法 | AES-256-GCM（自带认证标签） |
| 存储格式 | `base64(iv || tag || ciphertext)` |
| 透明加解密 | ORM 层自动处理，Service 层拿到的始终是明文 |

### 1.5 不迁移的配置（保持环境变量）

| 配置组 | 环境变量 | 原因 |
|--------|---------|------|
| Server | `SERVER__SECRET_KEY`、`SERVER__PORT` | 启动前置依赖 |
| Database | `DATABASE__URL` | 连接 DB 本身需要 |
| Redis | `REDIS__URL` | 连接 Redis 本身需要 |
| Celery | `CELERY__BROKER_URL`、`CELERY__RESULT_BACKEND` | Worker 启动前置依赖 |
| LLM | `LLM__MODEL`、`LLM__API_KEY`、`LLM__API_BASE` | 可选二期迁移 |
| Review | `REVIEW__COMMENT_LANGUAGE` 等 | 应用行为参数，保留 env |

---

## 二、需要迁移的配置项清单

### 2.1 代码平台 → `platform_configs` 表

| platform | 字段 | 说明 | 加密 | 当前来源 |
|----------|------|------|------|---------|
| gitee | access_token | Gitee API 令牌 | 是 | env `CODE_REVIEW__GITEE__TOKEN` |
| gitee | webhook_secret | Webhook 签名密钥 | 是 | env `CODE_REVIEW__GITEE__WEBHOOK_SECRET` |
| gitee | api_url | API 地址 | 否 | 硬编码 `https://gitee.com/api/v5` |
| github | access_token | GitHub API 令牌 | 是 | env `CODE_REVIEW__GITHUB__TOKEN` |
| github | webhook_secret | Webhook 签名密钥 | 是 | env `CODE_REVIEW__GITHUB__WEBHOOK_SECRET` |
| github | api_url | API 地址 | 否 | 硬编码 `https://api.github.com` |
| gitlab | access_token | GitLab API 令牌 | 是 | env `CODE_REVIEW__GITLAB__TOKEN` |
| gitlab | webhook_secret | Webhook 签名密钥 | 是 | env `CODE_REVIEW__GITLAB__WEBHOOK_SECRET` |
| gitlab | api_url | API 地址 | 否 | env `CODE_REVIEW__GITLAB__API_URL` + 硬编码默认值 |

### 2.2 通知渠道 → `notification_configs` 表

| channel | 字段 | 说明 | 加密 | 当前来源 |
|---------|------|------|------|---------|
| dingtalk | enabled | 是否启用 | 否 | env `CODE_REVIEW__DINGTALK__ENABLED` |
| dingtalk | webhook_url | Webhook 地址 | 否 | env `CODE_REVIEW__DINGTALK__WEBHOOK_URL` |
| dingtalk | secret | 签名密钥 | 是 | env `CODE_REVIEW__DINGTALK__SECRET` |
| dingtalk | at_mobiles | @人手机号 | 否 | **新增**，当前代码未支持 |
| feishu | enabled | 是否启用 | 否 | env `CODE_REVIEW__FEISHU__ENABLED` |
| feishu | webhook_url | Webhook 地址 | 否 | env `CODE_REVIEW__FEISHU__WEBHOOK_URL` |
| feishu | secret | 签名密钥 | 是 | env `CODE_REVIEW__FEISHU__SECRET` |

---

## 三、需要改造的代码模块清单

### 3.1 新增文件

| 文件 | 职责 |
|------|------|
| `src/code_review/models/db.py` 新增 `PlatformConfig` ORM | platform_configs 表映射 |
| `src/code_review/models/db.py` 新增 `NotificationConfig` ORM | notification_configs 表映射 |
| `src/code_review/services/platform_config_service.py` | 平台配置 CRUD + 缓存 |
| `src/code_review/services/notification_config_service.py` | 通知配置 CRUD + 缓存 |
| `src/code_review/api/platform_config.py` | 平台配置 REST API |
| `src/code_review/api/notification_config.py` | 通知配置 REST API |
| `src/code_review/infrastructure/config_crypto.py` | AES-256-GCM 加解密 |
| `configs/migrations/003_platform_and_notification_configs.sql` | 建表 + 种子数据 |

### 3.2 配置消费层改造

| 文件 | 行号 | 当前读取方式 | 改造后 |
|------|------|------------|--------|
| `adapters/factory.py` L34-L37 | `create_adapter()` GitHub | `config.github.token` / `.api_url` / `.webhook_secret` | `PlatformConfigService.get_by_platform("github")` |
| `adapters/factory.py` L40-L46 | `create_adapter()` GitLab | `config.gitlab.*` | `PlatformConfigService.get_by_platform("gitlab")` |
| `adapters/factory.py` L48-L54 | `create_adapter()` Gitee | `config.gitee.*` | `PlatformConfigService.get_by_platform("gitee")` |
| `infrastructure/notification_manager.py` L21-L38 | `_init_channels()` | `config.feishu` / `config.dingtalk` 对象传入 | `NotificationConfigService` 查 DB |
| `infrastructure/notification_feishu.py` L20-L23 | `FeishuChannel.__init__()` | 接收 `FeishuConfig` Pydantic 对象 | 改为接收 `NotificationConfig` ORM 对象或 dict |
| `infrastructure/notification_feishu.py` L31 | `FeishuChannel.enabled` | `self._config.enabled` | 同上 |
| `infrastructure/notification_dingtalk.py` L20-L23 | `DingTalkChannel.__init__()` | 接收 `DingTalkConfig` 对象 | 同上 |
| `infrastructure/notification_dingtalk.py` L31 | `DingTalkChannel.enabled` | `self._config.enabled` | 同上 |
| `infrastructure/notification_email.py` L18-L56 | `EmailChannel.__init__()` | 接收 `EmailConfig` 对象 | 同上（本方案暂不改造 Email） |

### 3.3 配置传递层改造

| 文件 | 行号 | 当前行为 | 改造后 |
|------|------|---------|--------|
| `api/app.py` L74 | `ReviewOrchestrator(config)` | 传 AppConfig 全局对象 | 注入 Service 实例 |
| `api/app.py` L75 | `NotificationManager(config)` | 同上 | 注入 Service 实例 |
| `services/review_orchestrator.py` L166 | `create_adapter(platform, config)` | 传 AppConfig | 传 `PlatformConfigService` |
| `worker.py` L24 | `AppConfig()` + `ReviewOrchestrator(config)` | 每任务创建 | 注入 Service |

### 3.4 配置定义层（最终清理）

| 文件 | 类 | 处理 |
|------|---|------|
| `models/config.py` L10 | `PlatformConfig` | 删除（与 DB 模型同名，需 rename） |
| `models/config.py` L17 | `GitHubConfig` | 删除 |
| `models/config.py` L22 | `GitLabConfig` | 删除 |
| `models/config.py` L27 | `GiteeConfig` | 删除 |
| `models/config.py` L42 | `FeishuConfig` | 删除 |
| `models/config.py` L49 | `DingTalkConfig` | 删除 |
| `models/config.py` L112 | `AppConfig` | 移除 github/gitlab/gitee/feishu/dingtalk 字段 |

---

## 四、REST API 接口设计

### 4.1 代码平台配置 API

基础路径：`/api/v1/platform-configs`

#### 查询所有平台配置

```bash
curl -s http://localhost:8000/api/v1/platform-configs
```

**响应 200：**

```json
[
  {
    "id": "uuid-xxx",
    "platform": "gitee",
    "access_token": "********",
    "webhook_secret": "********",
    "api_url": "https://gitee.com/api/v5",
    "enabled": true,
    "description": "Gitee 代码平台",
    "created_at": "2026-04-15T10:00:00",
    "updated_at": "2026-04-15T10:00:00"
  }
]
```

> 敏感字段默认返回 `********`，加 `?reveal=true` 返回真实值。

#### 按平台查询

```bash
curl -s http://localhost:8000/api/v1/platform-configs/gitee
```

**响应 200：** 单条 JSON。**404：** `{"detail": "Platform 'gitee' not found"}`

#### 更新平台配置

```bash
curl -s -X PUT http://localhost:8000/api/v1/platform-configs/gitee \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "new_token_value",
    "webhook_secret": "new_secret",
    "enabled": true
  }'
```

**请求体（所有字段可选）：**

```json
{
  "access_token": "string, optional",
  "webhook_secret": "string, optional",
  "api_url": "string, optional",
  "enabled": "boolean, optional",
  "description": "string, optional"
}
```

**响应 200：** 返回更新后的完整对象。**404：** 平台不存在。

#### 创建平台配置（新增平台类型时使用）

```bash
curl -s -X POST http://localhost:8000/api/v1/platform-configs \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "gitee",
    "access_token": "8b575cbce5ab3b7238604bb057ac30f4",
    "webhook_secret": "Pt5atRs53jGVBe8fwiyV",
    "api_url": "https://gitee.com/api/v5",
    "description": "Gitee 代码平台"
  }'
```

**响应 201：** 返回完整对象。**409：** `{"detail": "Platform 'gitee' already exists"}`

#### 删除平台配置

```bash
curl -s -X DELETE http://localhost:8000/api/v1/platform-configs/gitee
```

**响应 204：** 无内容。

#### 批量导入平台配置

```bash
curl -s -X POST http://localhost:8000/api/v1/platform-configs/import \
  -H "Content-Type: application/json" \
  -d '{
    "overwrite": true,
    "configs": [
      {
        "platform": "gitee",
        "access_token": "8b575cbce5ab3b7238604bb057ac30f4",
        "webhook_secret": "Pt5atRs53jGVBe8fwiyV",
        "api_url": "https://gitee.com/api/v5"
      },
      {
        "platform": "github",
        "access_token": "",
        "webhook_secret": "",
        "api_url": "https://api.github.com"
      }
    ]
  }'
```

**响应 200：**

```json
{
  "imported": 2,
  "skipped": 0,
  "errors": []
}
```

---

### 4.2 通知渠道配置 API

基础路径：`/api/v1/notification-configs`

#### 查询所有渠道配置

```bash
curl -s http://localhost:8000/api/v1/notification-configs
```

**响应 200：**

```json
[
  {
    "id": "uuid-xxx",
    "channel": "dingtalk",
    "enabled": false,
    "webhook_url": "",
    "secret": "********",
    "at_mobiles": "",
    "description": "钉钉机器人通知",
    "created_at": "2026-04-15T10:00:00",
    "updated_at": "2026-04-15T10:00:00"
  },
  {
    "id": "uuid-yyy",
    "channel": "feishu",
    "enabled": false,
    "webhook_url": "",
    "secret": "********",
    "at_mobiles": "",
    "description": "飞书机器人通知",
    "created_at": "2026-04-15T10:00:00",
    "updated_at": "2026-04-15T10:00:00"
  }
]
```

#### 按渠道查询

```bash
curl -s http://localhost:8000/api/v1/notification-configs/dingtalk
```

#### 更新渠道配置

```bash
curl -s -X PUT http://localhost:8000/api/v1/notification-configs/dingtalk \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=xxx",
    "secret": "SECxxx",
    "at_mobiles": "13800138000,13900139000"
  }'
```

#### 创建渠道配置

```bash
curl -s -X POST http://localhost:8000/api/v1/notification-configs \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "dingtalk",
    "enabled": false,
    "webhook_url": "",
    "secret": "",
    "description": "钉钉机器人通知"
  }'
```

#### 删除渠道配置

```bash
curl -s -X DELETE http://localhost:8000/api/v1/notification-configs/feishu
```

#### 批量导入渠道配置

```bash
curl -s -X POST http://localhost:8000/api/v1/notification-configs/import \
  -H "Content-Type: application/json" \
  -d '{
    "overwrite": false,
    "configs": [
      {
        "channel": "dingtalk",
        "enabled": false,
        "webhook_url": "",
        "secret": ""
      },
      {
        "channel": "feishu",
        "enabled": false,
        "webhook_url": "",
        "secret": ""
      }
    ]
  }'
```

---

## 五、改造步骤和执行顺序

```
步骤 1  建表 + ORM 模型 + 加密工具
  ↓
步骤 2  Service 层（CRUD + 缓存）
  ↓
步骤 3  API 层 + 批量导入
  ↓
步骤 4  改造消费层（适配器工厂 + 通知管理器）
  ↓
步骤 5  数据迁移 + 降级开关
  ↓
步骤 6  测试验证
  ↓
步骤 7  清理旧代码 + 移除 env 依赖
```

### 步骤 1：建表 + ORM + 加密

**产出：**
- `configs/migrations/003_platform_and_notification_configs.sql`
- `models/db.py` 新增 `PlatformConfig` 和 `NotificationConfig`（注意：当前 `config.py` 中有个同名 `PlatformConfig`，需先 rename 为 `EnvPlatformConfig` 或直接删除）
- `infrastructure/config_crypto.py` — `encrypt(plaintext) -> str`、`decrypt(ciphertext) -> str`

**验证：** 启动应用，表自动创建，种子数据插入成功。

### 步骤 2：Service 层

**产出：**
- `services/platform_config_service.py`

```python
class PlatformConfigService:
    async def get_by_platform(self, platform: str) -> PlatformConfig | None
    async def get_all(self) -> list[PlatformConfig]
    async def create(self, platform, access_token, webhook_secret, api_url, ...) -> PlatformConfig
    async def update(self, platform, **fields) -> PlatformConfig | None
    async def delete(self, platform) -> bool
    async def batch_import(self, configs: list[dict], overwrite=False) -> dict
    async def get_by_platform_with_fallback(self, platform: str, env_config) -> PlatformConfig
```

- `services/notification_config_service.py`

```python
class NotificationConfigService:
    async def get_by_channel(self, channel: str) -> NotificationConfig | None
    async def get_all(self) -> list[NotificationConfig]
    async def get_enabled(self) -> list[NotificationConfig]
    async def create(self, channel, ...) -> NotificationConfig
    async def update(self, channel, **fields) -> NotificationConfig | None
    async def delete(self, channel) -> bool
    async def batch_import(self, configs: list[dict], overwrite=False) -> dict
```

**缓存：** `get_by_platform()` / `get_by_channel()` 结果缓存 Redis TTL=300s，写操作时主动失效。

### 步骤 3：API 层

**产出：**
- `api/platform_config.py` — `/api/v1/platform-configs` 路由
- `api/notification_config.py` — `/api/v1/notification-configs` 路由
- `app.py` 注册两个路由

### 步骤 4：改造消费层

#### 4a. 改造 `factory.py`

```python
# 改造前
def create_adapter(platform, config, project_webhook_secret=""):
    match platform:
        case PlatformType.GITHUB:
            adapter = GitHubAdapter(token=config.github.token, api_url=config.github.api_url)

# 改造后
async def create_adapter(platform, platform_config_service, project_webhook_secret=""):
    pc = await platform_config_service.get_by_platform_with_fallback(
        platform.value, fallback_config
    )
    match platform:
        case PlatformType.GITHUB:
            adapter = GitHubAdapter(token=pc.access_token, api_url=pc.api_url)
```

#### 4b. 改造 `notification_manager.py`

```python
# 改造前
class NotificationManager:
    def _init_channels(self, config):
        channel = FeishuChannel(config.feishu)

# 改造后
class NotificationManager:
    async def _init_channels(self, notification_config_service):
        configs = await notification_config_service.get_enabled()
        for cfg in configs:
            if cfg.channel == "feishu":
                self._channels.append(FeishuChannel(cfg))
            elif cfg.channel == "dingtalk":
                self._channels.append(DingTalkChannel(cfg))
```

#### 4c. 改造 Channel `__init__`

```python
# 改造前
class FeishuChannel:
    def __init__(self, config: FeishuConfig):
        self._webhook_url = config.webhook_url

# 改造后（接收 ORM 对象或 dict）
class FeishuChannel:
    def __init__(self, config: NotificationConfig):
        self._webhook_url = config.webhook_url
        self._secret = config.secret
        self._enabled = config.enabled
```

### 步骤 5：数据迁移

1. 执行 `003_*.sql` 建表 + 种子空行
2. 调用批量导入 API，将 `.env` 中现有配置写入对应行
3. 降级开关生效：DB 有数据走 DB，空值降级走 env

### 步骤 6：测试验证

| 场景 | 验证点 |
|------|--------|
| 平台配置 CRUD | GET/POST/PUT/DELETE 正常 |
| 通知配置 CRUD | 同上 |
| 批量导入 | 覆盖/跳过逻辑正确 |
| Webhook 评审 | DB 中的 Gitee token 被正确使用 |
| 通知发送 | DB 中的渠道配置被正确读取 |
| 降级 | DB 值为空时回退到 env |
| 加密 | access_token 在 DB 中密文，API 返回脱敏 |
| 缓存 | 重复查询命中 Redis |

### 步骤 7：清理

- 删除 `config.py` 中的 `PlatformConfig`（env 版）、`GitHubConfig`、`GitLabConfig`、`GiteeConfig`、`FeishuConfig`、`DingTalkConfig`
- 从 `AppConfig` 移除 `github`/`gitlab`/`gitee`/`feishu`/`dingtalk` 字段
- 清理 `.env` 和 `docker-compose.yml` 中的平台/通知环境变量

---

## 六、向后兼容和回退策略

### 6.1 双读降级

```
get_by_platform_with_fallback("gitee", env_config)
    ↓
查 Redis 缓存 → 命中 → 返回
    ↓ 未命中
查 DB platform_configs → 有数据且非空 → 写缓存 → 返回
    ↓ 无数据或空值
降级到 env_config.gitee.token → 返回（不缓存）
```

### 6.2 灰度开关

环境变量 `CODE_REVIEW__CONFIG__SOURCE`：

| 值 | 行为 |
|----|------|
| `env`（默认） | 完全走环境变量（当前行为） |
| `db` | 完全走 DB |
| `hybrid` | 优先 DB，降级 env |

### 6.3 回退方案

| 场景 | 处理 |
|------|------|
| DB 启动不可用 | 自动降级 env，日志告警 |
| DB 运行时不可用 | Redis 缓存续命，缓存过期降级 env |
| 配置值为空 | `get_by_platform_with_fallback()` 返回 env 值 |
| 解密失败 | 日志告警，降级 env |
| 批量导入失败 | 事务回滚，已有数据不受影响 |

### 6.4 迁移时间线

```
Week 1  步骤 1-3：建表 + 服务 + API（无线上影响）
Week 2  步骤 4：改造消费层，hybrid 模式灰度
Week 3  步骤 5-6：数据迁移 + 全量测试
Week 4  步骤 7：清理旧代码，切换 db 模式
```
