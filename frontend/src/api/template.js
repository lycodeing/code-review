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

/** 获取项目的 Prompt 模板绑定列表 */
export function getProjectPromptBindings(projectId) {
  return request.get(`/projects/${projectId}/prompt-bindings`)
}

/** 创建项目 Prompt 模板绑定 */
export function createProjectPromptBinding(projectId, data) {
  return request.post(`/projects/${projectId}/prompt-bindings`, data)
}

/** 更新项目 Prompt 模板绑定 */
export function updateProjectPromptBinding(projectId, bindingId, data) {
  return request.put(`/projects/${projectId}/prompt-bindings/${bindingId}`, data)
}

/** 删除项目 Prompt 模板绑定 */
export function deleteProjectPromptBinding(projectId, bindingId) {
  return request.delete(`/projects/${projectId}/prompt-bindings/${bindingId}`)
}

/** 设置默认 Prompt 模板 */
export function setDefaultPromptBinding(projectId, bindingId) {
  return request.patch(`/projects/${projectId}/prompt-bindings/${bindingId}/set-default`)
}
