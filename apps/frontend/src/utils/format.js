import dayjs from 'dayjs'

/** 格式化日期时间 */
export function formatDateTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

/** 格式化日期 */
export function formatDate(value) {
  if (!value) return '-'
  return new Date(value).toLocaleDateString('zh-CN')
}

/** 截断文本 */
export function truncate(text, length = 50) {
  if (!text) return '-'
  return text.length > length ? text.substring(0, length) + '...' : text
}

/** 平台标签颜色映射 */
export const platformColors = {
  github: '#24292e',
  gitlab: '#FC6D26',
  gitee: '#C71D23'
}

/** 平台显示名称 */
export const platformNames = {
  github: 'GitHub',
  gitlab: 'GitLab',
  gitee: 'Gitee'
}

/** 评审状态映射 */
export const reviewStatusMap = {
  pending: { label: '等待中', type: 'info' },
  in_progress: { label: '评审中', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
  failed: { label: '失败', type: 'danger' },
  timeout: { label: '超时', type: 'danger' },
  skipped: { label: '已跳过', type: 'info' }
}

/** 严重程度映射 */
export const severityMap = {
  critical: { label: '严重', type: 'danger' },
  warning: { label: '警告', type: 'warning' },
  suggestion: { label: '建议', type: 'info' },
  info: { label: '提示', type: '' }
}
