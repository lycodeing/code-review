import request from './index'

/** 获取通知模板列表 */
export function getNotificationTemplates(params) {
  return request.get('/notification-templates', { params })
}

/** 获取通知模板详情 */
export function getNotificationTemplate(id) {
  return request.get(`/notification-templates/${id}`)
}

/** 创建通知模板 */
export function createNotificationTemplate(data) {
  return request.post('/notification-templates', data)
}

/** 更新通知模板 */
export function updateNotificationTemplate(id, data) {
  return request.put(`/notification-templates/${id}`, data)
}

/** 删除通知模板 */
export function deleteNotificationTemplate(id) {
  return request.delete(`/notification-templates/${id}`)
}

/** 预览通知模板渲染结果 */
export function previewNotificationTemplate(id, data) {
  return request.post(`/notification-templates/${id}/preview`, data)
}

/** 设置渠道默认模板 */
export function setChannelTemplate(channel, templateId) {
  return request.put(`/notification-configs/${channel}/template`, { template_id: templateId })
}

/** 获取项目的通知模板绑定 */
export function getProjectNotificationBindings(projectId) {
  return request.get(`/projects/${projectId}/notification-template-bindings`)
}

/** 批量设置项目的通知模板绑定 */
export function updateProjectNotificationBindings(projectId, bindings) {
  return request.put(`/projects/${projectId}/notification-template-bindings`, bindings)
}
