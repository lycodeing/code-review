import request from './index'

/** 查询全局 API 调用日志 */
export function getApiCallLogs(params) {
  return request.get('/logs', { params })
}

/** 获取单条评审的调用日志 */
export function getReviewLogs(taskId) {
  return request.get(`/reviews/${taskId}/logs`)
}
