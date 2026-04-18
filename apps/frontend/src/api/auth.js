import request from './index'

// 模拟登录（后端暂无认证接口）
export function login(data) {
  // 预设账号验证
  const { username, password } = data
  if (username === 'admin' && password === 'admin123') {
    return Promise.resolve({
      token: 'mock-token-' + Date.now(),
      user: { id: 1, username: 'admin', name: '管理员', role: 'admin' }
    })
  }
  return Promise.reject(new Error('用户名或密码错误'))
}

// 获取当前用户信息
export function getUserInfo() {
  return Promise.resolve({
    id: 1,
    username: 'admin',
    name: '管理员',
    role: 'admin',
    avatar: ''
  })
}
