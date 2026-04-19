<template>
  <div class="page-container">
    <!-- 过滤栏 -->
    <div class="filter-container">
      <el-form :model="filters" inline>
        <el-form-item label="类型">
          <el-select v-model="filters.call_type" placeholder="全部" clearable style="width: 130px">
            <el-option label="AI 调用" value="llm" />
            <el-option label="通知发送" value="notification" />
          </el-select>
        </el-form-item>
        <el-form-item label="结果">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failed" />
          </el-select>
        </el-form-item>
        <el-form-item label="提供商">
          <el-input v-model="filters.provider" placeholder="模型名/渠道名" clearable style="width: 160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="doSearch">
            <el-icon><Search /></el-icon> 搜索
          </el-button>
          <el-button @click="resetFilters">
            <el-icon><Refresh /></el-icon> 重置
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 表格 -->
    <div class="table-container">
      <div class="table-toolbar">
        <span class="table-title">请求历史</span>
        <div class="toolbar-actions">
          <el-button @click="doSearch">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </div>

      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="created_at" label="时间" width="175">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="call_type" label="类型" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="row.call_type === 'llm' ? 'primary' : 'success'" size="small">
              {{ row.call_type === 'llm' ? 'AI 调用' : '通知发送' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="provider" label="提供商" width="170" show-overflow-tooltip />
        <el-table-column prop="status" label="结果" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
              {{ row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="response_status" label="HTTP" width="75" align="center" />
        <el-table-column prop="duration_ms" label="耗时(ms)" width="95" align="right" />
        <el-table-column prop="url" label="URL" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span style="font-family: monospace; font-size: 12px">{{ row.url }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="error_message" label="错误信息" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.error_message" style="color: #F56C6C">{{ row.error_message }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="关联任务" width="100" align="center">
          <template #default="{ row }">
            <el-button
              v-if="row.task_id"
              text
              type="primary"
              size="small"
              @click="$router.push(`/reviews/${row.task_id}`)"
            >
              查看评审
            </el-button>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="详情" width="70" align="center">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="openDetail(row)">
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </div>

    <!-- 详情抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      title="调用详情"
      size="620px"
      direction="rtl"
    >
      <div v-if="selectedLog">
        <el-descriptions :column="2" border size="small" style="margin-bottom: 16px">
          <el-descriptions-item label="类型">
            <el-tag :type="selectedLog.call_type === 'llm' ? 'primary' : 'success'" size="small">
              {{ selectedLog.call_type === 'llm' ? 'AI 调用' : '通知发送' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="提供商">{{ selectedLog.provider }}</el-descriptions-item>
          <el-descriptions-item label="结果">
            <el-tag :type="selectedLog.status === 'success' ? 'success' : 'danger'" size="small">
              {{ selectedLog.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="HTTP状态码">{{ selectedLog.response_status ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ selectedLog.duration_ms }} ms</el-descriptions-item>
          <el-descriptions-item label="时间">{{ formatDateTime(selectedLog.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="URL" :span="2">
            <span style="word-break: break-all; font-family: monospace; font-size: 12px">
              {{ selectedLog.url || '-' }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item v-if="selectedLog.error_message" label="错误信息" :span="2">
            <span style="color: #F56C6C; white-space: pre-wrap">{{ selectedLog.error_message }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <el-collapse v-model="activeItems" style="margin-top: 8px">
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
import { ElMessage } from 'element-plus'
import { Search, Refresh } from '@element-plus/icons-vue'
import { getApiCallLogs } from '@/api/logs'
import { formatDateTime } from '@/utils/format'

const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const pagination = ref({ page: 1, pageSize: 20 })
const filters = ref({ call_type: '', status: '', provider: '' })

// 详情抽屉
const drawerVisible = ref(false)
const selectedLog = ref(null)
const activeItems = ref(['req_headers', 'req_body', 'resp_body'])

function openDetail(row) {
  selectedLog.value = row
  drawerVisible.value = true
}

function formatJson(obj) {
  if (!obj) return '(空)'
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

async function loadLogs() {
  loading.value = true
  try {
    const params = {
      offset: (pagination.value.page - 1) * pagination.value.pageSize,
      limit: pagination.value.pageSize,
    }
    if (filters.value.call_type) params.call_type = filters.value.call_type
    if (filters.value.status) params.status = filters.value.status
    if (filters.value.provider) params.provider = filters.value.provider

    const data = await getApiCallLogs(params)
    tableData.value = Array.isArray(data.items) ? data.items : []
    total.value = data.total ?? 0
  } catch (error) {
    ElMessage.error(error.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function doSearch() {
  pagination.value.page = 1
  loadLogs()
}

function resetFilters() {
  filters.value = { call_type: '', status: '', provider: '' }
  pagination.value.page = 1
  loadLogs()
}

function handlePageChange(page) {
  pagination.value.page = page
  loadLogs()
}

function handleSizeChange(size) {
  pagination.value.pageSize = size
  pagination.value.page = 1
  loadLogs()
}

onMounted(loadLogs)
</script>

<style lang="scss" scoped>
.table-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.toolbar-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
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
  max-height: 420px;
  overflow-y: auto;
}
</style>
