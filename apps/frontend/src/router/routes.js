// 路由表定义
const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/LoginView.vue'),
    meta: { title: '登录', hidden: true }
  },
  {
    path: '/',
    component: () => import('@/components/layout/AppLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/DashboardView.vue'),
        meta: { title: '仪表盘', icon: 'Odometer' }
      },
      {
        path: 'projects',
        name: 'Projects',
        component: () => import('@/views/project/ProjectList.vue'),
        meta: { title: '项目管理', icon: 'FolderOpened' }
      },
      {
        path: 'reviews',
        name: 'Reviews',
        component: () => import('@/views/review/ReviewList.vue'),
        meta: { title: '评审记录', icon: 'Document' }
      },
      {
        path: 'reviews/:id',
        name: 'ReviewDetail',
        component: () => import('@/views/review/ReviewDetail.vue'),
        meta: { title: '评审详情', hidden: true }
      },
      {
        path: 'templates',
        name: 'Templates',
        component: () => import('@/views/template/TemplateList.vue'),
        meta: { title: 'Prompt 模板', icon: 'Tickets' }
      },
      {
        path: 'platforms',
        name: 'Platforms',
        component: () => import('@/views/platform/PlatformList.vue'),
        meta: { title: '平台配置', icon: 'Connection' }
      },
      {
        path: 'notifications',
        name: 'Notifications',
        component: () => import('@/views/notification/NotificationList.vue'),
        meta: { title: '通知配置', icon: 'Bell' }
      },
      {
        path: 'notification-templates',
        name: 'NotificationTemplates',
        component: () => import('@/views/notification/NotificationTemplateList.vue'),
        meta: { title: '通知模板', icon: 'ChatDotSquare' }
      },
      {
        path: 'llm-configs',
        name: 'LLMConfigs',
        component: () => import('@/views/llm/LLMConfigList.vue'),
        meta: { title: 'LLM 配置', icon: 'Cpu' }
      },
      {
        path: 'review-rules',
        name: 'ReviewRules',
        component: () => import('@/views/rule/RuleList.vue'),
        meta: { title: '评审规则', icon: 'Filter' }
      },
      {
        path: 'system-settings',
        name: 'SystemSettings',
        component: () => import('@/views/system/TimeoutConfig.vue'),
        meta: { title: '系统配置', icon: 'Setting' }
      },
      {
        path: 'request-history',
        name: 'RequestHistory',
        component: () => import('@/views/log/ApiCallLogList.vue'),
        meta: { title: '请求历史', icon: 'List' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard'
  }
]

export default routes
