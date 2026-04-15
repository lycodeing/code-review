# Code Review 系统架构图与时序流程图

> 基于 Mermaid 语法，可直接在任何支持 Mermaid 的 Markdown 编辑器中渲染。

---

## 1. 系统架构图（组件关系与数据流向）

```mermaid
graph TB
    subgraph EXT["外部系统"]
        GITEE["Gitee / GitHub / GitLab<br/>代码托管平台"]
        LLM["LLM Provider<br/>DashScope · Qwen 3.6-plus"]
        FEISHU["飞书 / 钉钉 / 邮件<br/>即时通讯通知"]
        ADMIN["管理员 / CI<br/>REST API 调用方"]
    end

    subgraph NET["网络层（公网 → 内网）"]
        INTERNET((Internet))
        NGINX["Nginx<br/>*.lycodeing.cn 反代"]
        FRPS["frps<br/>lycodeing.cn:7000"]
        FRPC["frpc<br/>HTTP 隧道 → localhost:8000"]
    end

    subgraph DOCKER["Docker Compose 服务集群"]
        subgraph APP_SVC["app 服务 (FastAPI + Uvicorn)"]
            WEBHOOK["Webhook Handler<br/>/webhook/{platform}"]
            MGMT["Management API<br/>/api/v1/projects<br/>/api/v1/reviews<br/>/api/v1/prompt-templates"]
            ORCH_IN["ReviewOrchestrator<br/>process_webhook_event()"]
            FACTORY["Adapter Factory<br/>策略模式创建适配器"]
        end

        subgraph WORKER_SVC["worker 服务 (Celery ForkPoolWorker)"]
            CELERY["Celery Worker<br/>review 队列消费者"]
            ORCH_EXEC["ReviewOrchestrator<br/>execute_review()"]
            AGG["CommentAggregator<br/>评论聚合引擎"]
            PM["PromptTemplateManager<br/>模板热加载"]
            LLM_REV["LiteLLMReviewer<br/>AI 评审引擎"]
            NOTIF["NotificationManager<br/>通知调度器"]
        end

        subgraph ADAPTERS["平台适配器层 (Strategy Pattern)"]
            GA["GitHubAdapter<br/>HMAC-SHA256 · PR Review API"]
            GLA["GitLabAdapter<br/>Token 验证 · Position 评论"]
            GEA["GiteeAdapter<br/>HMAC 签名 · 批量评论"]
            BASE["BasePlatformAdapter<br/>httpx · tenacity 重试<br/>分页 · 速率限制"]
        end

        subgraph CHANNELS["通知渠道 (Strategy Pattern)"]
            FC["FeishuChannel<br/>消息卡片 · HMAC 签名"]
            DC["DingTalkChannel<br/>Markdown · 签名 URL"]
            EC["EmailChannel<br/>aiosmtplib（预留）"]
        end

        subgraph STORE["数据层"]
            PG[("PostgreSQL 16<br/>projects<br/>review_tasks<br/>review_comments<br/>prompt_templates")]
            RD[("Redis 7<br/>DB0: 缓存<br/>DB1: Celery Broker<br/>DB2: Celery Backend")]
            CACHE["TTLCache<br/>进程内事件去重<br/>TTL=3600s · max=10000"]
        end
    end

    %% === 外部请求流 ===
    GITEE -- "1. PR 事件 Webhook" --> INTERNET
    ADMIN -- "REST API" --> INTERNET
    INTERNET --> NGINX
    NGINX -- "2. cr.lycodeing.cn" --> FRPS
    FRPS -- "3. frp 隧道" --> FRPC
    FRPC -- "4. :8000" --> WEBHOOK
    ADMIN -. "API 直连 :8000" .-> MGMT

    %% === Webhook 处理流 ===
    WEBHOOK --> FACTORY
    FACTORY --> GEA
    WEBHOOK --> ORCH_IN
    ORCH_IN --> CACHE
    ORCH_IN --> PG
    ORCH_IN -- "send_task" --> RD

    %% === Celery 异步流 ===
    RD -- "6. 消费任务" --> CELERY
    CELERY --> ORCH_EXEC
    ORCH_EXEC --> FACTORY
    FACTORY --> GA & GLA & GEA
    GA & GLA & GEA --> BASE
    ORCH_EXEC --> PG
    ORCH_EXEC --> PM
    PM --> PG
    ORCH_EXEC --> LLM_REV
    ORCH_EXEC --> AGG
    ORCH_EXEC --> NOTIF
    ORCH_EXEC -. "5. 发布评论" .-> GITEE

    %% === LLM 调用 ===
    LLM_REV -- "LiteLLM acompletion" --> LLM

    %% === 平台 API 回调 ===
    BASE -- "get_mr_info / get_mr_changes" --> GITEE
    BASE -- "publish_comments_batch" --> GITEE

    %% === 通知发送 ===
    NOTIF --> FC & DC & EC
    FC & DC -- "Webhook POST" --> FEISHU

    %% === 样式 ===
    classDef external fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#92400e
    classDef network fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1e40af
    classDef service fill:#d1fae5,stroke:#059669,stroke-width:2px,color:#065f46
    classDef data fill:#ede9fe,stroke:#7c3aed,stroke-width:2px,color:#5b21b6
    classDef adapter fill:#fce7f3,stroke:#db2777,stroke-width:2px,color:#9d174d
    classDef channel fill:#fff7ed,stroke:#ea580c,stroke-width:2px,color:#9a3412

    class GITEE,LLM,FEISHU,ADMIN external
    class INTERNET,NGINX,FRPS,FRPC network
    class WEBHOOK,MGMT,ORCH_IN,FACTORY,CELERY,ORCH_EXEC,AGG,PM,LLM_REV,NOTIF service
    class GA,GLA,GEA,BASE adapter
    class FC,DC,EC channel
    class PG,RD,CACHE data
```

---

## 2. 端到端时序流程图

```mermaid
sequenceDiagram
    autonumber
    participant Dev as 开发者
    participant Gitee as Gitee
    participant Nginx as Nginx
    participant Frp as frp隧道
    participant App as FastAPI
    participant Cache as 去重缓存
    participant DB as PostgreSQL
    participant Redis as Redis
    participant Worker as Celery Worker
    participant Adapter as GiteeAdapter
    participant PM as 模板管理器
    participant LLM as LLM评审器
    participant Agg as 评论聚合器
    participant Notify as 通知管理器
    participant IM as 飞书/钉钉

    rect rgba(254,243,199,0.3)
    Note over Dev,Redis: 第一阶段 - Webhook接收与任务分发 约200ms
    Dev->>Gitee: 创建 Pull Request
    Gitee-->>Nginx: POST webhook 请求
    Nginx->>Frp: 反向代理
    Frp->>App: 隧道转发到 8000 端口
    Note over App: gitee_webhook 处理请求
    App->>Adapter: 创建适配器实例
    App->>Adapter: 验证 Webhook 签名
    Note right of Adapter: HMAC-SHA256 签名验证
    Adapter-->>App: 签名通过
    App->>Adapter: 解析 Webhook 事件
    Adapter-->>App: WebhookEvent 对象
    App->>Cache: 检查事件是否重复
    Cache-->>App: 首次事件
    App->>Cache: 写入去重标记 TTL 3600s
    App->>DB: 查询匹配的项目配置
    DB-->>App: 返回 Project 记录
    App->>DB: 创建 ReviewTask 记录
    DB-->>App: 返回 task_id
    App->>Redis: 投递 Celery 任务到 review 队列
    App->>DB: 更新 celery_task_id
    App-->>Gitee: 202 Accepted
    end

    rect rgba(209,250,229,0.3)
    Note over Redis,IM: 第二阶段 - Celery Worker 异步评审 约60-120s

    Redis-->>Worker: 消费 review 队列
    Note over Worker: asyncio.run 执行评审<br/>每次创建新 orchestrator

    Worker->>DB: 查询 ReviewTask
    DB-->>Worker: task 状态为 pending
    Worker->>DB: 更新状态为 in_progress
    Worker->>DB: 查询关联的 Project
    DB-->>Worker: 返回项目配置
    Worker->>Adapter: 创建平台适配器

    Note over Worker,Gitee: A 获取 PR 信息
    Worker->>Adapter: get_mr_info
    Adapter->>Gitee: GET pulls API
    Gitee-->>Adapter: PR 标题 作者 分支 状态
    Adapter-->>Worker: MRInfo 对象

    Note over Worker,Gitee: B 获取代码变更
    Worker->>Adapter: get_mr_changes
    Adapter->>Gitee: GET files API
    Gitee-->>Adapter: 文件变更列表
    Note right of Adapter: patch 兼容处理<br/>dict 提取 diff 键<br/>str 直接使用
    Adapter-->>Worker: FileChange 列表

    Note over Worker: 文件过滤 排除 lock vendor 等

    Note over Worker,DB: C 加载 Prompt 模板
    Worker->>PM: 检测文件语言类型
    PM-->>Worker: java
    Worker->>PM: 获取模板
    PM->>DB: 按优先级匹配模板
    Note right of PM: 匹配链<br/>1 项目指定名称<br/>2 java+zh<br/>3 java+任意<br/>4 default+zh<br/>5 default+任意
    DB-->>PM: java_zh 模板
    PM-->>Worker: 模板文本

    Note over Worker,LLM: D AI 评审 核心环节
    Worker->>Worker: 替换模板占位符
    Worker->>LLM: review 调用
    Note right of LLM: LiteLLM acompletion<br/>model: qwen3.6-plus<br/>api: dashscope<br/>temperature: 0.3
    LLM->>LLM: Qwen 推理中
    LLM-->>Worker: 返回 JSON 评审结果
    Note over Worker: 解析 JSON 响应<br/>提取评论列表<br/>映射严重等级枚举

    Note over Worker,Agg: E 评论聚合
    Worker->>Agg: aggregate
    Note right of Agg: 1 按文件和行号排序<br/>2 相邻5行合并<br/>3 按严重级别截断<br/>4 生成统计摘要
    Agg-->>Worker: 聚合后评论和摘要

    Note over Worker,Gitee: F 发布评论
    Worker->>Adapter: publish_comments_batch
    Note right of Adapter: 按级别分组格式化<br/>Critical > Warning<br/>Suggestion > Info<br/>每条含路径行号和代码建议
    Adapter->>Gitee: POST 评论到 PR
    Gitee-->>Adapter: comment_id
    Adapter-->>Worker: 发布成功

    Note over Worker,DB: G 持久化结果
    Worker->>DB: 批量插入 review_comments

    Note over Worker,IM: H 发送通知
    Worker->>Notify: notify_all
    Notify->>IM: 飞书卡片消息
    IM-->>Notify: OK
    Notify->>IM: 钉钉 Markdown 消息
    IM-->>Notify: OK
    Notify-->>Worker: 全部发送成功

    Note over Worker,DB: I 完成任务
    Worker->>DB: 更新状态为 completed
    Note right of DB: 写入 model_name<br/>total_comments<br/>critical_count<br/>warning_count<br/>summary
    Worker-->>Redis: Task succeeded
    end

    rect rgba(219,234,254,0.3)
    Note over Dev,IM: 第三阶段 - 结果可达
    Note over Dev,Gitee: 开发者在 PR 页面看到 AI 评审评论
    Note over Dev,IM: 团队在飞书或钉钉群收到评审通知
    end
```

---

## 3. 核心数据模型关系图

```mermaid
erDiagram
    Project ||--o{ ReviewTask : "has many"
    ReviewTask ||--o{ ReviewComment : "has many"
    PromptTemplate {
        uuid id PK
        varchar name UK "模板名称（唯一）"
        text content "模板内容 {{diff}} {{files_context}}"
        varchar category "分类: default/python/java/go"
        varchar locale "语言: zh/en"
        int enabled "1=启用 0=禁用"
        timestamp created_at
        timestamp updated_at
    }
    Project {
        uuid id PK
        varchar name UK "项目名称"
        varchar platform "github/gitlab/gitee"
        varchar platform_project_id "平台项目ID (owner/repo)"
        varchar webhook_secret "Webhook签名密钥"
        json config "项目级配置覆盖"
        int enabled "1=启用 0=禁用"
        timestamp created_at
        timestamp updated_at
    }
    ReviewTask {
        uuid id PK
        uuid project_id FK
        varchar mr_iid "PR展示编号"
        varchar mr_title
        varchar mr_author
        text mr_url
        varchar source_branch
        varchar target_branch
        varchar status "pending/in_progress/completed/failed"
        varchar event_id "幂等去重事件ID"
        varchar trigger_action "opened/synchronize/updated"
        varchar model_name "使用的LLM模型"
        int total_comments
        int critical_count
        int warning_count
        text summary
        text error_message
        varchar celery_task_id
        timestamp started_at
        timestamp completed_at
        timestamp created_at
    }
    ReviewComment {
        uuid id PK
        uuid task_id FK
        varchar file_path
        int line_start
        int line_end
        varchar severity "critical/warning/suggestion/info"
        text message
        text suggestion
        varchar platform_comment_id "平台评论ID"
        timestamp created_at
    }
```

---

## 4. Prompt 模板匹配优先级

```mermaid
flowchart TD
    START([get_template 调用]) --> CHECK_NAME{项目配置指定了<br/>template_name?}
    CHECK_NAME -- 是 --> FIND_BY_NAME[DB: SELECT WHERE name=指定名称]
    FIND_BY_NAME --> FOUND_NAME{找到且启用?}
    FOUND_NAME -- 是 --> RETURN_NAME[返回指定模板]
    FOUND_NAME -- 否 --> FIND_MATCH

    CHECK_NAME -- 否 --> FIND_MATCH[find_best_match 按优先级链查找]

    FIND_MATCH --> P1[① category + locale 精确匹配<br/>例: java + zh → java_zh]
    P1 --> P1_OK{找到?}
    P1_OK -- 是 --> RETURN_MATCH[返回匹配模板]

    P1_OK -- 否 --> P2[② category + 任意 locale<br/>例: java + * → java_en]
    P2 --> P2_OK{找到?}
    P2_OK -- 是 --> RETURN_MATCH

    P2_OK -- 否 --> P3[③ default + locale<br/>例: default + zh → default_zh]
    P3 --> P3_OK{找到?}
    P3_OK -- 是 --> RETURN_MATCH

    P3_OK -- 否 --> P4[④ default + 任意 locale<br/>例: default + * → default_en]
    P4 --> P4_OK{找到?}
    P4_OK -- 是 --> RETURN_MATCH

    P4_OK -- 否 --> FALLBACK[使用内置 BUILTIN_TEMPLATES 兜底]

    RETURN_NAME --> END([返回模板文本])
    RETURN_MATCH --> END
    FALLBACK --> END

    classDef decision fill:#fef3c7,stroke:#d97706
    classDef action fill:#d1fae5,stroke:#059669
    classDef fallback fill:#fee2e2,stroke:#dc2626
    class CHECK_NAME,FOUND_NAME,P1_OK,P2_OK,P3_OK,P4_OK decision
    class FIND_BY_NAME,FIND_MATCH,P1,P2,P3,P4,RETURN_NAME,RETURN_MATCH action
    class FALLBACK fallback
```

---

## 5. Docker 部署架构

```mermaid
graph LR
    subgraph HOST["宿主机"]
        subgraph DOCKER["Docker Compose"]
            APP["code-review-app<br/>FastAPI :8000<br/>uvicorn"]
            WORKER["code-review-worker<br/>Celery ForkPoolWorker<br/>concurrency=2"]
            DB["code-review-db<br/>PostgreSQL 16<br/>:5432"]
            REDIS["code-review-redis<br/>Redis 7<br/>:6379 (宿主 :6380)"]
        end
        FRPC["frpc<br/>HTTP 隧道<br/>→ localhost:8000"]
    end

    subgraph CLOUD["公网服务器 (lycodeing.cn)"]
        FRPS["frps :7000"]
        NGINX["Nginx<br/>*.lycodeing.cn → frps"]
    end

    INTERNET((Internet)) --> NGINX
    NGINX --> FRPS
    FRPS -. "TCP 隧道" .-> FRPC
    FRPC --> APP

    APP --- DB
    APP --- REDIS
    WORKER --- DB
    WORKER --- REDIS

    classDef svc fill:#d1fae5,stroke:#059669,stroke-width:2px
    classDef infra fill:#ede9fe,stroke:#7c3aed,stroke-width:2px
    classDef net fill:#dbeafe,stroke:#2563eb,stroke-width:2px
    class APP,WORKER svc
    class DB,REDIS infra
    class FRPC,FRPS,NGINX net
```
