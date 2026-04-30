<template>
  <div class="page-container">
    <el-page-header @back="$router.push('/reviews')" title="返回列表">
      <template #content>
        <span>评审详情</span>
        <StatusTag v-if="detail.status" :status="detail.status" style="margin-left: 8px" />
      </template>
      <template #extra>
        <div style="display: flex; gap: 8px; align-items: center">
          <el-button
            v-if="detail.status === 'failed' || detail.status === 'timeout'"
            type="warning"
            :loading="retrying"
            @click="handleRetry"
          >
            <el-icon><RefreshRight /></el-icon> 重试评审
          </el-button>
          <el-button
            v-if="detail.status === 'completed'"
            type="primary"
            plain
            :loading="notifying"
            @click="handleSendNotification"
          >
            <el-icon><Bell /></el-icon> 发送通知
          </el-button>
        </div>
      </template>
    </el-page-header>

    <!-- 评审历史版本面板 -->
    <el-card v-if="revisions.length > 0" shadow="never" class="revision-card">
      <template #header>
        <div class="revision-header">
          <div class="revision-title">
            <el-icon style="margin-right: 4px"><Clock /></el-icon>
            <span>评审历史</span>
            <el-tag size="small" type="info" style="margin-left: 8px">{{ revisions.length }} 个版本</el-tag>
          </div>
        </div>
      </template>
      <TransitionGroup name="revision-fade" tag="div" class="revision-list">
        <div
          v-for="rev in sortedRevisions"
          :key="rev.id"
          :class="['revision-item', { active: selectedRevision === rev.revision }]"
          @click="switchRevision(rev.revision)"
        >
          <div class="revision-left">
            <span class="revision-number">{{ String(rev.revision).padStart(2, '0') }}</span>
            <StatusTag :status="rev.status" />
          </div>
          <div class="revision-center">
            <span class="revision-date">{{ formatDate(rev.created_at) }}</span>
            <span class="revision-trigger">{{ rev.trigger_action }}</span>
          </div>
          <div class="revision-right">
            <span class="revision-model">{{ rev.model_name || '-' }}</span>
            <span class="revision-time">{{ formatTime(rev.created_at) }}</span>
          </div>
        </div>
      </TransitionGroup>
    </el-card>

    <div v-loading="loading" style="margin-top: 20px">
      <el-tabs v-model="activeTab">
        <!-- 基本信息 Tab -->
        <el-tab-pane label="基本信息" name="info">
          <el-card shadow="never" class="detail-card">
            <template #header>
              <span class="card-title">{{ detail.mr_title || '加载中...' }}</span>
            </template>
            <el-descriptions :column="3" border>
              <el-descriptions-item label="MR 标题">{{ detail.mr_title }}</el-descriptions-item>
              <el-descriptions-item label="作者">{{ detail.mr_author }}</el-descriptions-item>
              <el-descriptions-item label="状态">
                <StatusTag v-if="detail.status" :status="detail.status" />
              </el-descriptions-item>
              <el-descriptions-item label="源分支">{{ detail.source_branch }}</el-descriptions-item>
              <el-descriptions-item label="目标分支">{{ detail.target_branch }}</el-descriptions-item>
              <el-descriptions-item label="触发方式">{{ detail.trigger_action }}</el-descriptions-item>
              <el-descriptions-item label="LLM 模型">{{ detail.model_name }}</el-descriptions-item>
              <el-descriptions-item label="评论数">{{ detail.total_comments }}</el-descriptions-item>
              <el-descriptions-item label="严重/警告">{{ detail.critical_count }} / {{ detail.warning_count }}</el-descriptions-item>
              <el-descriptions-item label="MR 链接">
                <a v-if="detail.mr_url" :href="detail.mr_url" target="_blank" class="link-text">
                  {{ detail.mr_url }}
                </a>
                <span v-else>-</span>
              </el-descriptions-item>
              <el-descriptions-item label="创建时间">{{ formatDateTime(detail.created_at) }}</el-descriptions-item>
              <el-descriptions-item label="完成时间">{{ formatDateTime(detail.completed_at) }}</el-descriptions-item>
            </el-descriptions>

            <div v-if="detail.summary" class="summary-section">
              <h4>评审摘要</h4>
              <div class="summary-content md-content" v-html="renderMarkdown(detail.summary)" />
            </div>

            <el-alert
              v-if="detail.error_message"
              type="error"
              :title="detail.error_message"
              show-icon
              style="margin-top: 16px"
            />
          </el-card>
        </el-tab-pane>

        <!-- 评审评论 Tab -->
        <el-tab-pane :label="`评审评论 (${comments.length})`" name="comments">
          <el-card shadow="never" class="detail-card">
            <div v-if="comments.length" class="comment-filter-bar">
              <el-select v-model="commentSeverityFilter" placeholder="严重程度" clearable size="small" style="width: 140px">
                <el-option label="严重" value="critical" />
                <el-option label="警告" value="warning" />
                <el-option label="建议" value="suggestion" />
                <el-option label="信息" value="info" />
              </el-select>
              <el-input v-model="commentFileSearch" placeholder="搜索文件路径" clearable size="small" style="width: 240px; margin-left: 8px" />
              <el-radio-group v-model="commentViewMode" size="small" style="margin-left: auto">
                <el-radio-button value="flat">列表</el-radio-button>
                <el-radio-button value="grouped">按文件</el-radio-button>
              </el-radio-group>
            </div>

            <div v-if="comments.length && commentViewMode === 'flat'">
              <TransitionGroup name="comment-slide" tag="div">
                <div v-for="comment in filteredComments" :key="comment.id" class="comment-item">
                  <div class="comment-header">
                    <div class="comment-file">
                      <el-icon><Document /></el-icon>
                      <span>{{ comment.file_path }}</span>
                    </div>
                    <div class="comment-meta">
                      <StatusTag :status="comment.severity" type="severity" />
                      <span v-if="comment.line_start" class="line-range">
                        L{{ comment.line_start }}{{ comment.line_end !== comment.line_start ? ` - L${comment.line_end}` : '' }}
                      </span>
                    </div>
                  </div>
                  <div class="comment-body md-content" v-html="renderMarkdown(comment.message)" />
                  <div v-if="comment.suggestion" class="comment-suggestion">
                    <strong>建议修复：</strong>
                    <div class="md-content" v-html="renderMarkdown(comment.suggestion)" />
                  </div>
                  <div class="comment-feedback">
                    <el-button text size="small" :type="comment.feedback === 'thumbs_up' ? 'primary' : ''" @click="handleFeedback(comment, 'thumbs_up')">👍 有用</el-button>
                    <el-button text size="small" :type="comment.feedback === 'thumbs_down' ? 'danger' : ''" @click="handleFeedback(comment, 'thumbs_down')">👎 无用</el-button>
                  </div>
                </div>
              </TransitionGroup>
              <el-empty v-if="!filteredComments.length" description="没有匹配的评论" :image-size="60" />
            </div>

            <div v-if="comments.length && commentViewMode === 'grouped'">
              <el-collapse v-model="expandedFiles">
                <el-collapse-item
                  v-for="group in groupedComments"
                  :key="group.file"
                  :name="group.file"
                >
                  <template #title>
                    <div class="file-group-title">
                      <el-icon><Document /></el-icon>
                      <span class="file-group-name">{{ group.file }}</span>
                      <el-tag size="small" type="info" style="margin-left: 8px">{{ group.comments.length }}</el-tag>
                      <span v-if="group.maxSeverity === 'critical'" class="severity-badge critical">严重</span>
                      <span v-else-if="group.maxSeverity === 'warning'" class="severity-badge warning">警告</span>
                    </div>
                  </template>
                  <div v-for="comment in group.comments" :key="comment.id" class="comment-item">
                    <div class="comment-header">
                      <div class="comment-meta">
                        <StatusTag :status="comment.severity" type="severity" />
                        <span v-if="comment.line_start" class="line-range">
                          L{{ comment.line_start }}{{ comment.line_end !== comment.line_start ? ` - L${comment.line_end}` : '' }}
                        </span>
                      </div>
                    </div>
                    <div class="comment-body md-content" v-html="renderMarkdown(comment.message)" />
                    <div v-if="comment.suggestion" class="comment-suggestion">
                      <strong>建议修复：</strong>
                      <div class="md-content" v-html="renderMarkdown(comment.suggestion)" />
                    </div>
                    <div class="comment-feedback">
                      <el-button text size="small" :type="comment.feedback === 'thumbs_up' ? 'primary' : ''" @click="handleFeedback(comment, 'thumbs_up')">👍 有用</el-button>
                      <el-button text size="small" :type="comment.feedback === 'thumbs_down' ? 'danger' : ''" @click="handleFeedback(comment, 'thumbs_down')">👎 无用</el-button>
                    </div>
                  </div>
                </el-collapse-item>
              </el-collapse>
              <el-empty v-if="!groupedComments.length" description="没有匹配的评论" :image-size="60" />
            </div>

            <el-empty v-if="!comments.length" description="暂无评论" />
          </el-card>
        </el-tab-pane>

        <!-- 调用日志 Tab -->
        <el-tab-pane :label="`调用日志 (${logs.length})`" name="logs" lazy>
          <el-card shadow="never" class="detail-card">
            <div v-if="logsLoading" v-loading="true" style="min-height: 120px" />
            <template v-else-if="logs.length">
              <el-table :data="logs" stripe>
                <el-table-column prop="created_at" label="时间" width="175">
                  <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
                </el-table-column>
                <el-table-column prop="call_type" label="类型" width="100" align="center">
                  <template #default="{ row }">
                    <el-tag :type="row.call_type === 'llm' ? 'primary' : 'success'" size="small">
                      {{ row.call_type === 'llm' ? 'AI 调用' : '通知发送' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="provider" label="提供商" width="150" show-overflow-tooltip />
                <el-table-column prop="status" label="结果" width="90" align="center">
                  <template #default="{ row }">
                    <el-tag
                      :type="logStatusMap[row.status]?.type || 'info'"
                      size="small"
                      :class="{ 'status-pulse': row.status === 'in_progress' }"
                    >
                      <el-icon v-if="row.status === 'in_progress'" class="is-loading" style="margin-right: 2px"><Loading /></el-icon>
                      {{ logStatusMap[row.status]?.label || row.status }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="response_status" label="HTTP状态" width="90" align="center">
                  <template #default="{ row }">{{ row.response_status ?? '-' }}</template>
                </el-table-column>
                <el-table-column prop="duration_ms" label="耗时(ms)" width="95" align="right">
                  <template #default="{ row }">{{ row.duration_ms != null ? row.duration_ms : '-' }}</template>
                </el-table-column>
                <el-table-column prop="error_message" label="错误信息" min-width="160" show-overflow-tooltip />
                <el-table-column label="详情" width="70" align="center">
                  <template #default="{ row }">
                    <el-button text type="primary" size="small" @click="openLogDetail(row)">
                      查看
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </template>
            <el-empty v-else description="暂无调用日志" />
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 日志详情抽屉 -->
    <el-drawer
      v-model="logDrawerVisible"
      title="调用详情"
      size="600px"
      direction="rtl"
    >
      <div v-if="selectedLog">
        <el-descriptions :column="2" border size="small" style="margin-bottom: 16px">
          <el-descriptions-item label="类型">{{ selectedLog.call_type }}</el-descriptions-item>
          <el-descriptions-item label="提供商">{{ selectedLog.provider }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ selectedLog.status }}</el-descriptions-item>
          <el-descriptions-item label="HTTP状态码">{{ selectedLog.response_status }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ selectedLog.duration_ms }} ms</el-descriptions-item>
          <el-descriptions-item label="时间">{{ formatDateTime(selectedLog.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="URL" :span="2">
            <span style="word-break: break-all; font-family: monospace; font-size: 12px">{{ selectedLog.url }}</span>
          </el-descriptions-item>
          <el-descriptions-item v-if="selectedLog.error_message" label="错误" :span="2">
            <span style="color: #F56C6C">{{ selectedLog.error_message }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <el-collapse v-model="activeCollapseItems">
          <el-collapse-item title="请求头" name="req_headers">
            <pre class="json-block">{{ formatJson(selectedLog.request_headers) }}</pre>
          </el-collapse-item>
          <el-collapse-item title="请求体" name="req_body">
            <pre class="json-block">{{ formatJson(selectedLog.request_body) }}</pre>
          </el-collapse-item>
          <el-collapse-item title="响应内容" name="resp_body">
            <pre class="json-block">{{ formatJson(selectedLog.response_body) }}</pre>
          </el-collapse-item>
        </el-collapse>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { RefreshRight, Bell, Document, Clock, Loading } from '@element-plus/icons-vue'
import { getReview, getReviewComments, retryReview, sendReviewNotification, updateCommentFeedback, getReviewRevisions } from '@/api/reviews'
import { getReviewLogs } from '@/api/logs'
import { formatDateTime, callLogStatusMap as logStatusMap } from '@/utils/format'
import { renderMarkdown } from '@/utils/markdown'
import StatusTag from '@/components/common/StatusTag.vue'
import 'highlight.js/styles/github-dark.css'

const route = useRoute()
const loading = ref(true)
const detail = ref({})
const comments = ref([])
const logs = ref([])
const logsLoading = ref(false)
const activeTab = ref('info')
const retrying = ref(false)
const notifying = ref(false)
const revisions = ref([])
const selectedRevision = ref(null)

const logDrawerVisible = ref(false)
const selectedLog = ref(null)
const activeCollapseItems = ref(['req_headers', 'req_body', 'resp_body'])

const commentSeverityFilter = ref('')
const commentFileSearch = ref('')
const commentViewMode = ref('flat')
const expandedFiles = ref([])

const severityOrder = { critical: 4, warning: 3, suggestion: 2, info: 1 }

const sortedRevisions = computed(() => {
  return [...revisions.value].sort((a, b) => b.revision - a.revision)
})

const filteredComments = computed(() => {
  let data = comments.value
  if (commentSeverityFilter.value) {
    data = data.filter(c => c.severity === commentSeverityFilter.value)
  }
  if (commentFileSearch.value) {
    const keyword = commentFileSearch.value.toLowerCase()
    data = data.filter(c => c.file_path.toLowerCase().includes(keyword))
  }
  return data
})

const groupedComments = computed(() => {
  const filtered = filteredComments.value
  const groupMap = new Map()
  for (const c of filtered) {
    if (!groupMap.has(c.file_path)) {
      groupMap.set(c.file_path, [])
    }
    groupMap.get(c.file_path).push(c)
  }
  const groups = []
  for (const [file, fileComments] of groupMap) {
    const maxSeverity = fileComments.reduce(
      (max, c) => (severityOrder[c.severity] || 0) > (severityOrder[max] || 0) ? c.severity : max,
      'info'
    )
    groups.push({ file, comments: fileComments, maxSeverity })
  }
  groups.sort((a, b) => (severityOrder[b.maxSeverity] || 0) - (severityOrder[a.maxSeverity] || 0))
  return groups
})

function formatDate(dt) {
  if (!dt) return '-'
  const d = new Date(dt)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function formatTime(dt) {
  if (!dt) return '-'
  const d = new Date(dt)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

const statusLabel = { completed: '完成', failed: '失败', pending: '等待中', in_progress: '进行中', timeout: '超时', cancelled: '已取消' }

function openLogDetail(row) {
  selectedLog.value = row
  logDrawerVisible.value = true
}

async function handleFeedback(comment, value) {
  const newFeedback = comment.feedback === value ? null : value
  try {
    await updateCommentFeedback(comment.id, newFeedback)
    comment.feedback = newFeedback
  } catch { /* 忽略 */ }
}

function formatJson(obj) {
  if (!obj) return '(空)'
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

async function loadDetail() {
  loading.value = true
  try {
    const id = route.params.id

    // 并行加载详情和版本列表
    const [taskData, revisionsData] = await Promise.all([
      getReview(id).catch(() => null),
      getReviewRevisions(id).catch(() => []),
    ])

    if (!taskData) {
      ElMessage.error('评审记录不存在')
      loading.value = false
      return
    }

    detail.value = taskData
    revisions.value = Array.isArray(revisionsData) ? revisionsData : []

    // 默认选中最新版本
    if (revisions.value.length > 0) {
      const latest = revisions.value.reduce((a, b) => (a.revision > b.revision ? a : b))
      selectedRevision.value = latest.revision
    }

    // 加载当前版本的数据
    await loadRevisionData(selectedRevision.value)
  } catch (e) {
    console.error('加载评审详情失败:', e)
  } finally {
    loading.value = false
  }
}

async function loadRevisionData(revision) {
  const id = route.params.id
  try {
    // 对于只有 1 个版本（revision=1，无子版本）的旧记录，不传 revision 参数
    const hasMultipleRevisions = revisions.value.length > 1
    const revParam = hasMultipleRevisions ? revision : undefined

    const [commentsData, logsData] = await Promise.all([
      getReviewComments(id, revParam).catch(() => []),
      getReviewLogs(id, revParam).catch(() => []),
    ])
    comments.value = Array.isArray(commentsData) ? commentsData : []
    logs.value = Array.isArray(logsData) ? logsData : []
  } catch (e) {
    console.error('加载版本数据失败:', e)
    comments.value = []
    logs.value = []
  }
}

async function switchRevision(revision) {
  if (revision === selectedRevision.value) return
  loading.value = true
  selectedRevision.value = revision
  try {
    await loadRevisionData(revision)
    const revTask = revisions.value.find(r => r.revision === revision)
    if (revTask) {
      detail.value = { ...detail.value, ...{
        status: revTask.status,
        trigger_action: revTask.trigger_action,
        model_name: revTask.model_name,
        total_comments: revTask.total_comments,
        critical_count: revTask.critical_count,
        warning_count: revTask.warning_count,
        summary: revTask.summary,
        error_message: revTask.error_message,
        started_at: revTask.started_at,
        completed_at: revTask.completed_at,
      }}
    }
  } catch {
    // 拦截器已处理
  } finally {
    loading.value = false
  }
}

async function loadLogs() {
  logsLoading.value = true
  try {
    const hasMultipleRevisions = revisions.value.length > 1
    const revParam = hasMultipleRevisions ? selectedRevision.value : undefined
    const data = await getReviewLogs(route.params.id, revParam)
    logs.value = Array.isArray(data) ? data : []
  } catch {
    // ignore
  } finally {
    logsLoading.value = false
  }
}

async function handleRetry() {
  retrying.value = true
  try {
    // 立即将状态更新为评审中
    detail.value = { ...detail.value, status: 'in_progress', error_message: null }
    // 同步更新版本列表中对应记录的状态
    const latestRev = revisions.value.reduce((a, b) => a.revision > b.revision ? a : b, revisions.value[0])
    if (latestRev) {
      latestRev.status = 'in_progress'
      latestRev.error_message = null
    }

    await retryReview(route.params.id)
    ElMessage.success('已重新提交评审任务')
  } catch (error) {
    // 失败时回滚状态
    detail.value = { ...detail.value, status: 'failed', error_message: error.message || '重试失败' }
    ElMessage.error(error.message || '重试失败')
  } finally {
    retrying.value = false
  }
}

async function handleSendNotification() {
  notifying.value = true
  try {
    const result = await sendReviewNotification(route.params.id)
    const total = result.sent + result.failed
    if (result.sent > 0) {
      ElMessage.success(`通知已发送：${result.sent}/${total} 个渠道成功`)
    } else {
      ElMessage.warning(`通知发送失败，请检查通知渠道配置`)
    }
    await loadLogs()
  } catch (error) {
    ElMessage.error(error.message || '发送通知失败')
  } finally {
    notifying.value = false
  }
}

onMounted(loadDetail)
</script>

<style lang="scss" scoped>
.detail-card {
  border-radius: $border-radius;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.link-text {
  color: $primary-color;
  word-break: break-all;
}

.summary-section {
  margin-top: 20px;

  h4 {
    font-size: 14px;
    color: #303133;
    margin-bottom: 8px;
  }
}

.summary-content {
  background: #f5f7fa;
  padding: 12px 16px;
  border-radius: $border-radius;
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
  white-space: pre-wrap;
}

.comment-item {
  padding: 16px;
  border: 1px solid #ebeef5;
  border-radius: $border-radius;
  margin-bottom: 12px;
  transition: box-shadow 0.2s;

  &:hover {
    box-shadow: $card-shadow;
  }
}

.comment-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.comment-file {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #303133;
  font-family: monospace;
}

.comment-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.line-range {
  font-size: 12px;
  color: #909399;
  font-family: monospace;
}

.comment-body {
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
}

.md-content {
  font-size: 14px;
  line-height: 1.7;

  :deep(p) { margin: 4px 0; }
  :deep(ul), :deep(ol) { padding-left: 20px; margin: 6px 0; }
  :deep(li) { margin: 2px 0; }
  :deep(strong) { font-weight: 600; }
  :deep(code) {
    background: #f5f5f5;
    color: #1a1a1a;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: monospace;
    font-size: 13px;
    border: 1px solid #d0d0d0;
  }
  :deep(.hljs-block) {
    margin: 8px 0;
    border-radius: 6px;
    overflow: hidden;
    code {
      display: block;
      padding: 12px;
      font-size: 13px;
      line-height: 1.5;
      overflow-x: auto;
      background: transparent;
    }
  }
}

.comment-suggestion {
  margin-top: 10px;
  padding: 10px 12px;
  background: #f0f9eb;
  border-radius: 4px;
  font-size: 13px;

  strong {
    color: #67C23A;
    display: block;
    margin-bottom: 6px;
  }
}

.json-block {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 400px;
  overflow-y: auto;
}

.comment-filter-bar {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
  gap: 8px;
}

.file-group-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.file-group-name {
  font-family: monospace;
  color: #303133;
}

.severity-badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
  margin-left: 4px;
  font-weight: 600;
  &.critical { background: #fef0f0; color: #f56c6c; }
  &.warning { background: #fdf6ec; color: #e6a23c; }
}

// 评审历史面板
.revision-card {
  margin-top: 16px;
  border-radius: $border-radius;
  border: 1px solid #e4e7ed;

  :deep(.el-card__header) {
    padding: 12px 20px;
    background: #f5f7fa;
  }

  :deep(.el-card__body) {
    padding: 8px;
  }
}

.revision-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.revision-title {
  display: flex;
  align-items: center;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.revision-list {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 4px 0;
}

.revision-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border: 2px solid #e4e7ed;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
  min-width: 180px;
  flex-shrink: 0;

  &:hover {
    border-color: #c0c4cc;
    background: #fafafa;
  }

  &.active {
    border-color: #409eff;
    background: #ecf5ff;
    box-shadow: 0 0 0 1px #409eff;
  }
}

.revision-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.revision-number {
  font-size: 18px;
  font-weight: 700;
  color: #606266;
  font-family: monospace;
  min-width: 22px;
  text-align: center;

  .active & {
    color: #409eff;
  }
}

.revision-center {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.revision-trigger {
  font-size: 12px;
  color: #909399;
}

.revision-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.revision-date {
  font-size: 12px;
  color: #606266;
  font-weight: 500;
}

.revision-model {
  font-size: 11px;
  color: #909399;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.revision-time {
  font-size: 11px;
  color: #c0c4cc;
}

// 评审历史版本过渡动画
.revision-fade-enter-active {
  transition: all 0.3s ease-out;
}
.revision-fade-leave-active {
  transition: all 0.2s ease-in;
}
.revision-fade-enter-from {
  opacity: 0;
  transform: translateX(20px);
}
.revision-fade-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}
.revision-fade-move {
  transition: transform 0.3s ease;
}

// 评论列表过渡动画
.comment-slide-enter-active {
  transition: all 0.3s ease-out;
}
.comment-slide-leave-active {
  transition: all 0.2s ease-in;
}
.comment-slide-enter-from {
  opacity: 0;
  transform: translateY(10px);
}
.comment-slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

// 调用日志状态动画
.status-pulse {
  animation: pulse-opacity 1.5s ease-in-out infinite;
}

:deep(.is-loading) {
  animation: spin-anim 1s linear infinite;
}

@keyframes spin-anim {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes pulse-opacity {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
</style>
