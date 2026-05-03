import request from '@/api/index'

/** 健康检查 */
export function checkHealth() {
  return request.get('/health')
}
