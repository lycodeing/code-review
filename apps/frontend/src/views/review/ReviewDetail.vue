<template>
  <div class="page-container">
    <el-page-header @back="$router.push('/reviews')" title="返回列表">
      <template #content>
        <span>评审详情</span>
        <StatusTag v-if="detail.status" :status="detail.status" style="margin-left: 8px" />
      </template>
      <template #extra>
        <div style="display: flex; gap: 8px">
          <el-button
            v-if="detail.status === 'failed'"
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
              <div class="summary-content">{{ detail.summary }}</div>
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
            <div v-if="comments.length">
              <div v-for="comment in comments" :key="comment.id" class="comment-item">
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
              </div>
            </div>
            <el-empty v-else description="暂无评论" />
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
                    <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
                      {{ row.status === 'success' ? '成功' : '失败' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="response_status" label="HTTP状态" width="90" align="center" />
                <el-table-column prop="duration_ms" label="耗时(ms)" width="95" align="right" />
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
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { RefreshRight, Bell, Document } from '@element-plus/icons-vue'
import { getReview, getReviewComments, retryReview, sendReviewNotification } from '@/api/reviews'
import { getReviewLogs } from '@/api/logs'
import { formatDateTime } from '@/utils/format'
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

// 日志抽屉
const logDrawerVisible = ref(false)
const selectedLog = ref(null)
const activeCollapseItems = ref(['req_headers', 'req_body', 'resp_body'])

function openLogDetail(row) {
  selectedLog.value = row
  logDrawerVisible.value = true
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
    const [taskData, commentsData, logsData] = await Promise.all([
      getReview(id),
      getReviewComments(id),
      getReviewLogs(id)
    ])
    detail.value = taskData
    comments.value = Array.isArray(commentsData) ? commentsData : []
    logs.value = Array.isArray(logsData) ? logsData : []
  } catch {
    // 拦截器已处理
  } finally {
    loading.value = false
  }
}

async function loadLogs() {
  logsLoading.value = true
  try {
    const data = await getReviewLogs(route.params.id)
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
    await retryReview(route.params.id)
    ElMessage.success('已重新提交评审任务')
    await loadDetail()
  } catch (error) {
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
    // 刷新日志
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
</style>
