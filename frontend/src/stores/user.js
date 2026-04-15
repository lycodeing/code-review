import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as loginApi } from '@/api/auth'
import { setToken, setUser, getToken, getUser, clearAuth } from '@/utils/auth'

export const useUserStore = defineStore('user', () => {
  const token = ref(getToken() || '')
  const userInfo = ref(getUser() || {})

  /** 登录 */
  async function login(loginForm) {
    const data = await loginApi(loginForm)
    token.value = data.token
    userInfo.value = data.user
    setToken(data.token)
    setUser(data.user)
    return data
  }

  /** 登出 */
  function logout() {
    token.value = ''
    userInfo.value = {}
    clearAuth()
  }

  /** 获取用户名 */
  function getUsername() {
    return userInfo.value?.name || userInfo.value?.username || ''
  }

  return { token, userInfo, login, logout, getUsername }
})
