import request from './index'

/** 获取平台配置列表 */
export function getPlatforms() {
  return request.get('/platform-configs')
}

/** 获取平台配置详情 */
export function getPlatform(platform) {
  return request.get(`/platform-configs/${platform}`)
}

/** 创建平台配置 */
export function createPlatform(data) {
  return request.post('/platform-configs', data)
}

/** 更新平台配置 */
export function updatePlatform(platform, data) {
  return request.put(`/platform-configs/${platform}`, data)
}

/** 删除平台配置 */
export function deletePlatform(platform) {
  return request.delete(`/platform-configs/${platform}`)
}

/** 导入平台配置 */
export function importPlatforms(data) {
  return request.post('/platform-configs/import', data)
}
