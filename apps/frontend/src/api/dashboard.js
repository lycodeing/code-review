import request from './index'

export function getDashboardStats(params = {}) {
  if (typeof params === 'string') params = { period: params }
  return request.get('/dashboard/stats', { params })
}

export function getDashboardTrend(days = 14) {
  return request.get('/dashboard/trend', { params: { days } })
}
