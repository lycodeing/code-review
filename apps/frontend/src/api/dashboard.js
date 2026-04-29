import request from './index'

export function getDashboardStats(period = 'all') {
  return request.get('/dashboard/stats', { params: { period } })
}

export function getDashboardTrend(days = 14) {
  return request.get('/dashboard/trend', { params: { days } })
}
