import request from './index'

/** 获取通知配置列表 */
export function getNotifications() {
  return request.get('/notification-configs')
}

/** 获取通知配置详情 */
export function getNotification(channel) {
  return request.get(`/notification-configs/${channel}`)
}

/** 创建通知配置 */
export function createNotification(data) {
  return request.post('/notification-configs', data)
}

/** 更新通知配置 */
export function updateNotification(channel, data) {
  return request.put(`/notification-configs/${channel}`, data)
}

/** 删除通知配置 */
export function deleteNotification(channel) {
  return request.delete(`/notification-configs/${channel}`)
}

/** 配置通知绑定 */
export function updateBinding(channel, data) {
  return request.put(`/notification-configs/${channel}/bindings`, data)
}

/** 导入通知配置 */
export function importNotifications(data) {
  return request.post('/notification-configs/import', data)
}
