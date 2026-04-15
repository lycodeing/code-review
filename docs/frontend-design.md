# Code Review Admin - 前端技术文档

## 1. 项目概述

基于 Vue 3 的 AI Code Review 后台管理系统，提供项目管理、评审记录查看、Prompt 模板管理、平台配置和通知渠道配置等功能。

## 2. 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue 3 | ^3.5 | 核心框架 (Composition API + `<script setup>`) |
| Vite | ^6.x | 构建工具 |
| Pinia | ^2.x | 状态管理 |
| Vue Router | ^4.x | 路由管理 |
| Element Plus | ^2.x | UI 组件库 |
| Axios | ^1.x | HTTP 请求 |
| ECharts | ^5.x | 图表库 |
| @vueuse/core | ^12.x | 组合式工具函数 |

## 3. 目录结构

```
frontend/
├── public/                          # 静态资源
│   └── favicon.ico
├── src/
│   ├── api/                         # API 请求模块
│   │   ├── index.js                 # Axios 实例、拦截器、错误处理
│   │   ├── auth.js                  # 认证相关 API（预留）
│   │   ├── project.js               # 项目 CRUD API
│   │   ├── review.js                # 评审记录 API
│   │   ├── template.js              # Prompt 模板 API
│   │   ├── platform.js              # 平台配置 API
│   │   └── notification.js          # 通知配置 API
│   ├── assets/                      # 静态资源
│   │   └── styles/
│   │       ├── variables.scss        # SCSS 变量（颜色、间距等）
│   │       ├── reset.scss            # 样式重置
│   │       ├── global.scss           # 全局样式
│   │       └── element-override.scss # Element Plus 样式覆盖
│   ├── components/                  # 公共组件
│   │   ├── common/
│   │   │   ├── SvgIcon.vue          # SVG 图标组件
│   │   │   ├── ConfirmDialog.vue    # 确认对话框
│   │   │   └── StatusTag.vue        # 状态标签
│   │   └── layout/
│   │       ├── AppLayout.vue        # 主布局容器
│   │       ├── Sidebar.vue          # 侧边栏
│   │       ├── Header.vue           # 顶部导航
│   │       └── TabsView.vue         # 标签页导航
│   ├── composables/                 # 组合式函数
│   │   ├── useTable.js              # 表格通用逻辑（分页、搜索、排序）
│   │   └── usePermission.js         # 权限检查
│   ├── router/                      # 路由
│   │   ├── index.js                 # 路由实例和守卫
│   │   └── routes.js                # 路由表定义
│   ├── stores/                      # Pinia Store
│   │   ├── user.js                  # 用户状态
│   │   ├── app.js                   # 应用全局状态（侧边栏折叠等）
│   │   └── tabs.js                  # 标签页状态
│   ├── utils/                       # 工具函数
│   │   ├── auth.js                  # Token 存储
│   │   └── format.js               # 格式化工具
│   └── views/                       # 页面
│       ├── login/
│       │   └── LoginView.vue
│       ├── dashboard/
│       │   └── DashboardView.vue
│       ├── project/
│       │   ├── ProjectList.vue
│       │   └── ProjectForm.vue
│       ├── review/
│       │   ├── ReviewList.vue
│       │   └── ReviewDetail.vue
│       ├── template/
│       │   ├── TemplateList.vue
│       │   └── TemplateForm.vue
│       ├── platform/
│       │   ├── PlatformList.vue
│       │   └── PlatformForm.vue
│       └── notification/
│           ├── NotificationList.vue
│           ├── NotificationForm.vue
│           └── BindingConfig.vue
├── index.html
├── vite.config.js
├── package.json
└── .env.development                 # 开发环境变量
```

## 4. 后端 API 对接

### 4.1 基础配置

- API 基础路径: `/api/v1`
- 代理配置: Vite dev server 代理到后端 `http://localhost:8000`
- 无需认证 Token（后端当前无鉴权机制，预留 Token 拦截器）

### 4.2 API 端点映射

| 模块 | 方法 | 端点 | 说明 |
|------|------|------|------|
| **项目** | GET | `/api/v1/projects` | 项目列表（支持 `?enabled=` 筛选） |
| | GET | `/api/v1/projects/{id}` | 项目详情 |
| | POST | `/api/v1/projects` | 创建项目 |
| | PUT | `/api/v1/projects/{id}` | 更新项目 |
| | DELETE | `/api/v1/projects/{id}` | 删除项目 |
| **评审** | GET | `/api/v1/reviews` | 评审列表（支持 `?project_id=&status=&limit=&offset=`） |
| | GET | `/api/v1/reviews/{id}` | 评审详情 |
| | GET | `/api/v1/reviews/{id}/comments` | 评审评论 |
| **模板** | GET | `/api/v1/prompt-templates` | 模板列表（分页） |
| | GET | `/api/v1/prompt-templates/{id}` | 模板详情 |
| | POST | `/api/v1/prompt-templates` | 创建模板 |
| | PUT | `/api/v1/prompt-templates/{id}` | 更新模板 |
| | DELETE | `/api/v1/prompt-templates/{id}` | 删除模板 |
| **平台** | GET | `/api/v1/platform-configs` | 平台列表 |
| | GET | `/api/v1/platform-configs/{platform}` | 平台详情（含通知绑定） |
| | POST | `/api/v1/platform-configs` | 创建平台配置 |
| | PUT | `/api/v1/platform-configs/{platform}` | 更新平台配置 |
| | DELETE | `/api/v1/platform-configs/{platform}` | 删除平台配置 |
| **通知** | GET | `/api/v1/notification-configs` | 通知渠道列表 |
| | GET | `/api/v1/notification-configs/{channel}` | 通知详情（含平台绑定） |
| | POST | `/api/v1/notification-configs` | 创建通知配置 |
| | PUT | `/api/v1/notification-configs/{channel}` | 更新通知配置 |
| | DELETE | `/api/v1/notification-configs/{channel}` | 删除通知配置 |
| | PUT | `/api/v1/notification-configs/{channel}/bindings` | 配置通知绑定 |
| **健康** | GET | `/api/v1/health` | 系统健康检查 |

## 5. 路由设计

```
/login                    # 登录页
/                         # 主布局（需要登录）
├── /dashboard            # 仪表盘首页
├── /projects             # 项目管理
├── /reviews              # 评审记录
│   └── /reviews/:id      # 评审详情
├── /templates            # Prompt 模板管理
├── /platforms            # 平台配置
└── /notifications        # 通知配置
```

## 6. 配色方案

```
主色调:   #409EFF (Element Plus 默认蓝)
成功色:   #67C23A
警告色:   #E6A23C
危险色:   #F56C6C
信息色:   #909399
背景色:   #F5F7FA
侧边栏:  #304156 (深蓝灰)
侧边栏文字: #BFDBFE
顶部栏:   #FFFFFF
卡片背景: #FFFFFF
```

## 7. 关键交互设计

### 7.1 布局
- 侧边栏: 固定在左侧，支持折叠（宽 210px / 窄 64px）
- 顶部栏: 展开收起按钮、面包屑、全屏切换、用户头像下拉
- 标签页: 支持右键关闭（关闭当前/关闭其他/关闭所有）
- 页面切换: 使用 `<transition>` 添加淡入动画

### 7.2 表格通用功能
- 分页: 前端分页或后端分页切换
- 搜索: 顶部搜索栏，支持关键词模糊搜索
- 筛选: 下拉筛选状态、类型等字段
- 排序: 点击表头排序
- 操作列: 编辑、删除（带确认提示）

### 7.3 表单通用功能
- 必填校验、格式校验
- 提交时 loading 状态
- 成功/失败提示

## 8. 登录机制

当前后端无认证系统，前端采用模拟登录方案：
- 默认账号: admin / admin123
- 登录后将 token 存储到 localStorage
- 路由守卫检查 token，无 token 则跳转登录页
- 预留后端认证接口，后续可无缝切换
