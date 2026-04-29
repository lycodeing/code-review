import request from './index'

/** 获取规则列表 */
export function getRules() {
  return request.get('/review-rules')
}

/** 创建规则 */
export function createRule(data) {
  return request.post('/review-rules', data)
}

/** 更新规则 */
export function updateRule(id, data) {
  return request.put(`/review-rules/${id}`, data)
}

/** 删除规则 */
export function deleteRule(id) {
  return request.delete(`/review-rules/${id}`)
}

/** 获取内置模板规则列表 */
export function getTemplates() {
  return request.get('/review-rules/templates')
}

/** 从内置模板导入规则 */
export function importTemplates(ruleIds) {
  return request.post('/review-rules/import-templates', { rule_ids: ruleIds })
}
