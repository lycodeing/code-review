import { createRouter, createWebHistory } from 'vue-router'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'
import routes from './routes'
import { getToken } from '@/utils/auth'

NProgress.configure({ showSpinner: false })

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 白名单路径（无需登录）
const whiteList = ['/login']

router.beforeEach((to, _from, next) => {
  NProgress.start()

  const token = getToken()
  if (token) {
    if (to.path === '/login') {
      next({ path: '/' })
    } else {
      next()
    }
  } else {
    if (whiteList.includes(to.path)) {
      next()
    } else {
      next(`/login?redirect=${to.path}`)
    }
  }
})

router.afterEach(() => {
  NProgress.done()
})

export default router
