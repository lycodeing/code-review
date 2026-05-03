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
  skipped: { label: '已跳过', type: 'info' },
  cancelled: { label: '已取消', type: 'info' }
}

/** 严重程度映射 */
export const severityMap = {
  critical: { label: '严重', type: 'danger' },
  warning: { label: '警告', type: 'warning' },
  suggestion: { label: '建议', type: 'info' },
  info: { label: '提示', type: '' }
}

/** 调用日志状态映射 */
export const callLogStatusMap = {
  success: { label: '成功', type: 'success' },
  failed: { label: '失败', type: 'danger' },
  in_progress: { label: '请求中', type: 'warning' },
  timeout: { label: '超时', type: 'danger' },
  pending: { label: '等待中', type: 'info' },
}

/** 调用类型映射 */
export const callTypeMap = {
  llm: { label: 'AI 调用', type: 'primary' },
  notification: { label: '通知发送', type: 'success' },
}

/** LLM 提供商标签颜色映射 */
export const providerColors = {
  openai: '#10a37f',
  anthropic: '#d4a574',
  deepseek: '#6366f1',
  ollama: '#000000',
  azure: '#0078d4',
  bedrock: '#232f3e',
  dashscope: '#ff6a00'
}

/** LLM 提供商显示名称 */
export const providerNames = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  deepseek: 'DeepSeek',
  ollama: 'Ollama',
  azure: 'Azure',
  bedrock: 'AWS Bedrock',
  dashscope: 'Dashscope (阿里云)',
  zhipu: '智谱 AI (Zhipu)'
}

/** 通知渠道名称 */
export const channelNames = {
  dingtalk: '钉钉',
  feishu: '飞书',
  wecom: '企业微信',
  slack: 'Slack'
}

/** 通知渠道图标和颜色 */
export const channelIcons = {
  dingtalk: { icon: 'ChatDotRound', color: '#0089FF' },
  feishu: { icon: 'ChatLineRound', color: '#3370FF' },
  wecom: { icon: 'ChatDotRound', color: '#07C160' },
  slack: { icon: 'ChatLineRound', color: '#4A154B' }
}

/** 响应格式标签 */
export const responseFormatLabels = {
  auto: '自动检测',
  json: 'JSON',
  anthropic_thinking: 'Anthropic Thinking',
  xml: 'XML',
  plain_text: '纯文本'
}

/** 响应格式标签类型 */
export const responseFormatTypes = {
  auto: 'info',
  json: 'success',
  anthropic_thinking: 'warning',
  xml: '',
  plain_text: 'info'
}

/** 格式化 JSON 对象为可读字符串 */
export function formatJson(obj) {
  if (!obj) return '(空)'
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}
