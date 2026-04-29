# 仪表盘统计功能设计文档

## 1. 背景与问题

当前仪表盘（`DashboardView.vue`）通过 `getReviews({ limit: 100 })` 拉取最近 100 条评审记录，在前端做聚合计算。存在以下问题：

- **数据不完整**：仅取最近 100 条，无法反映真实的周/月统计
- **性能瓶颈**：数据量增长后前端聚合越来越慢
- **缺少时间维度**：没有周统计、月统计、同比/环比等分析能力

## 2. 目标

- 新增后端统计聚合 API，由 PostgreSQL 直接完成聚合计算
- 前端仪表盘支持「本周 / 本月 / 全部」三种统计视角切换
- 趋势图支持 7 天 / 14 天 / 30 天切换
- 新增严重程度分布饼图和项目排行

## 3. 数据模型分析

统计数据来源于以下表：

| 表 | 关键字段 | 用途 |
|---|---|---|
| `review_tasks` | `status`, `created_at`, `project_id`, `critical_count`, `warning_count`, `total_comments` | 评审数量、状态分布、严重程度统计 |
| `review_comments` | `severity`, `task_id`, `created_at` | 评论级别分布（补充 task 级别统计） |
| `projects` | `id`, `name`, `platform` | 项目维度聚合 |

已有索引：`ix_review_status`（status）、`review_tasks.created_at`（无索引，需新增）。

## 4. API 设计

### 4.1 统计概览接口

```
GET /api/v1/dashboard/stats?period=week
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `period` | string | `all` | 统计周期：`week`（本周）/ `month`（本月）/ `all`（全部） |

**响应：**

```json
{
  "overview": {
    "total_projects": 12,
    "total_reviews": 358,
    "completed": 320,
    "failed": 38,
    "in_progress": 0
  },
  "period_stats": {
    "period": "week",
    "start_date": "2026-04-21",
    "end_date": "2026-04-27",
    "review_count": 45,
    "completed": 40,
    "failed": 5,
    "critical_count": 12,
    "warning_count": 28,
    "suggestion_count": 35,
    "info_count": 10,
    "avg_comments_per_review": 6.2
  },
  "severity_distribution": [
    {"severity": "critical", "count": 12},
    {"severity": "warning", "count": 28},
    {"severity": "suggestion", "count": 35},
    {"severity": "info", "count": 10}
  ],
  "top_projects": [
    {"project_id": "uuid", "project_name": "backend-api", "review_count": 20},
    {"project_id": "uuid", "project_name": "frontend", "review_count": 15}
  ]
}
```

### 4.2 趋势数据接口

```
GET /api/v1/dashboard/trend?days=14
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `days` | int | `14` | 趋势天数：`7` / `14` / `30` |

**响应：**

```json
{
  "days": 14,
  "data": [
    {
      "date": "2026-04-14",
      "total": 8,
      "completed": 7,
      "failed": 1,
      "critical": 3,
      "warning": 5
    }
  ]
}
```

## 5. 后端实现方案

### 5.1 新增文件

`apps/backend/src/code_review/api/dashboard.py` — 仪表盘统计路由

### 5.2 SQL 聚合查询

**概览统计（按周期过滤）：**

```sql
SELECT
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE status = 'completed') AS completed,
    COUNT(*) FILTER (WHERE status = 'failed') AS failed,
    COALESCE(SUM(critical_count), 0) AS critical_total,
    COALESCE(SUM(warning_count), 0) AS warning_total,
    COALESCE(SUM(total_comments), 0) AS comments_total
FROM review_tasks
WHERE created_at >= :start_date;
```

**趋势数据（按天聚合）：**

```sql
SELECT
    DATE(created_at AT TIME ZONE 'UTC') AS date,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE status = 'completed') AS completed,
    COUNT(*) FILTER (WHERE status = 'failed') AS failed,
    COALESCE(SUM(critical_count), 0) AS critical,
    COALESCE(SUM(warning_count), 0) AS warning
FROM review_tasks
WHERE created_at >= NOW() - INTERVAL ':days days'
GROUP BY DATE(created_at AT TIME ZONE 'UTC')
ORDER BY date;
```

**项目排行：**

```sql
SELECT
    p.id AS project_id,
    p.name AS project_name,
    COUNT(rt.id) AS review_count
FROM review_tasks rt
JOIN projects p ON p.id = rt.project_id
WHERE rt.created_at >= :start_date
GROUP BY p.id, p.name
ORDER BY review_count DESC
LIMIT 5;
```

### 5.3 数据库索引

需新增索引以支持按时间范围聚合：

```sql
CREATE INDEX ix_review_tasks_created_at ON review_tasks (created_at);
```

### 5.4 路由注册

在 `app.py` 中注册新路由：

```python
from code_review.api.dashboard import router as dashboard_router
app.include_router(dashboard_router)
```

## 6. 前端实现方案

### 6.1 新增 API 模块

`apps/frontend/src/api/dashboard.js`：

```javascript
import request from './index'

export function getDashboardStats(period = 'all') {
  return request.get('/api/v1/dashboard/stats', { params: { period } })
}

export function getDashboardTrend(days = 14) {
  return request.get('/api/v1/dashboard/trend', { params: { days } })
}
```

### 6.2 DashboardView.vue 改造

**统计卡片区域：**
- 增加 `el-radio-group` 切换「本周 / 本月 / 全部」
- 卡片数据从后端 `overview` + `period_stats` 获取
- 新增卡片：评论总数、严重问题数

**趋势图区域：**
- 增加 `el-radio-group` 切换「7天 / 14天 / 30天」
- 折线图改为双线：已完成（绿）+ 失败（红）
- 数据从 `/dashboard/trend` 获取

**新增区域：**
- 严重程度分布饼图（使用已注册的 `PieChart`）
- 项目评审排行（水平柱状图或表格）

### 6.3 UI 布局

```
┌─────────────────────────────────────────────────┐
│  [本周] [本月] [全部]                              │
├──────┬──────┬──────┬──────┬──────┬──────┐       │
│项目数 │评审数 │已完成 │失败数 │严重  │评论数 │       │
└──────┴──────┴──────┴──────┴──────┴──────┘       │
├────────────────────────┬────────────────────────┤
│  评审趋势 [7d][14d][30d]│  严重程度分布（饼图）     │
│  ~~~~~~~~~/\~~~        │      ◉ critical 12     │
│  ~~~~~~~~/  \~~        │      ◉ warning  28     │
│  ~~~~~~~    ~~~~       │      ◉ suggestion 35   │
│                        │      ◉ info     10     │
├────────────────────────┼────────────────────────┤
│  项目评审排行 Top 5      │  最近评审                │
│  backend-api    ████ 20│  feat: xxx  completed  │
│  frontend       ███ 15 │  fix: yyy   failed     │
│  mobile-app     ██ 10  │  ...                   │
├────────────────────────┴────────────────────────┤
│  系统状态                                         │
└─────────────────────────────────────────────────┘
```

## 7. 迁移脚本

`apps/backend/migrations/add_dashboard_index.sql`：

```sql
-- 仪表盘统计查询优化索引
CREATE INDEX IF NOT EXISTS ix_review_tasks_created_at
    ON review_tasks (created_at);

CREATE INDEX IF NOT EXISTS ix_review_tasks_project_created
    ON review_tasks (project_id, created_at);
```

## 8. 实现步骤

| 步骤 | 内容 | 涉及文件 |
|------|------|----------|
| 1 | 新增数据库索引迁移脚本 | `migrations/add_dashboard_index.sql` |
| 2 | 实现后端统计 API | `api/dashboard.py` |
| 3 | 注册路由 | `api/app.py` |
| 4 | 新增前端 API 模块 | `api/dashboard.js` |
| 5 | 改造 DashboardView | `views/dashboard/DashboardView.vue` |
| 6 | 移除旧的前端聚合逻辑 | `views/dashboard/DashboardView.vue` |

## 9. 测试要点

- 空数据场景：无评审记录时各统计值为 0
- 时间边界：周一 00:00 UTC 作为本周起点
- 大数据量：1000+ 评审记录时 API 响应 < 200ms
- 趋势图无数据日期：应补零而非跳过
