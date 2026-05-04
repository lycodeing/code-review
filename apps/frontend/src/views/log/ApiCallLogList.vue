<template>
  <div class="page-container">
    <!-- 过滤栏 -->
    <div class="filter-container">
      <el-form :model="filters" inline>
        <el-form-item label="类型">
          <el-select v-model="filters.call_type" placeholder="全部" clearable style="width: 130px">
            <el-option
              v-for="item in callTypeOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="结果">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 120px">
            <el-option
              v-for="item in callLogStatusOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
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
            <el-tag :type="callTypeMap[row.call_type]?.type || 'info'" size="small">
              {{ callTypeMap[row.call_type]?.label || row.call_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="provider" label="提供商" width="170" show-overflow-tooltip />
        <el-table-column prop="status" label="结果" width="120" align="center">
          <template #default="{ row }">
            <el-tag
              :type="callLogStatusMap[row.status]?.type || 'info'"
              size="small"
              :class="{ 'status-pulse': row.status === 'in_progress' }"
            >
              <el-icon v-if="row.status === 'in_progress'" class="is-loading" style="margin-right: 2px"><Loading /></el-icon>
              {{ callLogStatusMap[row.status]?.label || row.status }}
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
    <LogDetailDrawer
      v-model:visible="drawerVisible"
      :log="selectedLog"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Search, Refresh, Loading } from '@element-plus/icons-vue'
import { getApiCallLogs } from '@/api/logs'
import { formatDateTime, callLogStatusMap, callTypeMap, mapToOptions } from '@/utils/format'
import { useTable } from '@/composables/useTable'
import LogDetailDrawer from '@/components/common/LogDetailDrawer.vue'

const callTypeOptions = mapToOptions(callTypeMap)
const callLogStatusOptions = mapToOptions(callLogStatusMap)
const filters = ref({ call_type: '', status: '', provider: '' })

const { loading, tableData, total, pagination, loadData, handlePageChange, handleSizeChange, resetPagination } = useTable(getApiCallLogs)

// 详情抽屉
const drawerVisible = ref(false)
const selectedLog = ref(null)

function openDetail(row) {
  selectedLog.value = row
  drawerVisible.value = true
}

function buildFilterParams() {
  const params = {}
  if (filters.value.call_type) params.call_type = filters.value.call_type
  if (filters.value.status) params.status = filters.value.status
  if (filters.value.provider) params.provider = filters.value.provider
  return params
}

async function doSearch() {
  resetPagination()
  loadData(buildFilterParams())
}

function resetFilters() {
  filters.value = { call_type: '', status: '', provider: '' }
  resetPagination()
  loadData()
}

onMounted(() => loadData())
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
</style>
