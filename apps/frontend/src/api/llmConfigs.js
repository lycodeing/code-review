import request from './index'

/** 获取 LLM 配置列表 */
export function getLLMConfigs(enabledOnly = false) {
  return request.get('/llm-configs', { params: { enabled_only: enabledOnly } })
}

/** 获取 LLM 配置详情 */
export function getLLMConfig(id) {
  return request.get(`/llm-configs/${id}`)
}

/** 创建 LLM 配置 */
export function createLLMConfig(data) {
  return request.post('/llm-configs', data)
}

/** 更新 LLM 配置 */
export function updateLLMConfig(id, data) {
  return request.put(`/llm-configs/${id}`, data)
}

/** 删除 LLM 配置 */
export function deleteLLMConfig(id) {
  return request.delete(`/llm-configs/${id}`)
}

/** 启用/禁用 LLM 配置 */
export function toggleLLMConfig(id, enabled) {
  return request.patch(`/llm-configs/${id}/enable`, { enabled })
}

/** 测试 LLM 配置连接（新建时使用，传入明文 API Key） */
export function testLLMConnection(data) {
  return request.post('/llm-configs/test-connection', data)
}

/** 测试已有 LLM 配置连接（按 ID，后端解密真实 Key） */
export function testLLMConnectionById(configId) {
  return request.post(`/llm-configs/${configId}/test`)
}

/** 获取项目的 LLM 绑定列表 */
export function getProjectLLMBindings(projectId) {
  return request.get(`/projects/${projectId}/llm-bindings`)
}

/** 创建项目 LLM 绑定 */
export function createProjectLLMBinding(projectId, data) {
  return request.post(`/projects/${projectId}/llm-bindings`, data)
}

/** 更新项目 LLM 绑定 */
export function updateProjectLLMBinding(projectId, bindingId, data) {
  return request.put(`/projects/${projectId}/llm-bindings/${bindingId}`, data)
}

/** 删除项目 LLM 绑定 */
export function deleteProjectLLMBinding(projectId, bindingId) {
  return request.delete(`/projects/${projectId}/llm-bindings/${bindingId}`)
}

/** 设置默认 LLM 配置 */
export function setDefaultLLMBinding(projectId, bindingId) {
  return request.patch(`/projects/${projectId}/llm-bindings/${bindingId}/set-default`)
}
