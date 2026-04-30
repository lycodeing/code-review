import request from './index'

export function getSystemSettings() {
  return request.get('/system-settings')
}

export function getSystemSettingCategories() {
  return request.get('/system-settings/categories')
}

export function getSystemSettingsByCategory(category) {
  return request.get(`/system-settings/category/${category}`)
}

export function updateSystemSettings(data) {
  return request.put('/system-settings', data)
}
