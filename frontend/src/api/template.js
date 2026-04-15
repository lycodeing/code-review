import request from './index'

/** 获取模板列表 */
export function getTemplates(params) {
  return request.get('/prompt-templates', { params })
}

/** 获取模板详情 */
export function getTemplate(id) {
  return request.get(`/prompt-templates/${id}`)
}

/** 创建模板 */
export function createTemplate(data) {
  return request.post('/prompt-templates', data)
}

/** 更新模板 */
export function updateTemplate(id, data) {
  return request.put(`/prompt-templates/${id}`, data)
}

/** 删除模板 */
export function deleteTemplate(id) {
  return request.delete(`/prompt-templates/${id}`)
}
