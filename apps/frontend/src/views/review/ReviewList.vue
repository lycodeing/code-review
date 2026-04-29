<template>
  <div class="page-container">
    <!-- 搜索栏 -->
    <div class="filter-container">
      <el-form :model="filters" inline>
        <el-form-item label="项目">
          <el-select v-model="filters.project_id" placeholder="全部" clearable style="width: 200px">
            <el-option
              v-for="p in projectOptions"
              :key="p.id"
              :label="p.name"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 140px">
            <el-option label="等待中" value="pending" />
            <el-option label="评审中" value="in_progress" />
            <el-option label="已完成" value="completed" />
            <el-option label="失败" value="failed" />
          </el-select>
        </el-form-item>
        <el-form-item label="MR 标题">
          <el-input v-model="filters.keyword" placeholder="搜索" clearable style="width: 180px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData(filters)">
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
        <span class="table-title">评审记录</span>
        <div class="toolbar-actions">
          <el-button type="primary" @click="openManualReviewDialog">
            <el-icon><Plus /></el-icon> 手动添加评审
          </el-button>
          <el-button @click="openDateRangeDialog">
            <el-icon><Delete /></el-icon> 按日期删除
          </el-button>
          <el-button
            type="danger"
            :disabled="selectedIds.length === 0"
            @click="handleBatchDelete"
          >
            <el-icon><Delete /></el-icon> 批量删除 ({{ selectedIds.length }})
          </el-button>
          <el-button
            type="warning"
            :disabled="selectedIds.length === 0"
            @click="handleBatchRetry"
          >
            <el-icon><RefreshRight /></el-icon> 批量重试 ({{ selectedIds.length }})
          </el-button>
          <el-button type="danger" plain @click="handleClearAll">
            <el-icon><Delete /></el-icon> 清空所有
          </el-button>
          <el-button @click="loadData(filters)">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </div>

      <el-table
        :data="filteredData"
        v-loading="loading"
        stripe
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" align="center" />
        <el-table-column prop="mr_title" label="MR 标题" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="link-text" @click="$router.push(`/reviews/${row.id}`)">{{ row.mr_title }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="mr_author" label="作者" width="100" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <StatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column prop="total_comments" label="评论数" width="90" align="center" />
        <el-table-column prop="critical_count" label="严重" width="80" align="center">
          <template #default="{ row }">
            <span :class="{ 'text-danger': row.critical_count > 0 }">{{ row.critical_count }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="warning_count" label="警告" width="80" align="center">
          <template #default="{ row }">
            <span :class="{ 'text-warning': row.warning_count > 0 }">{{ row.warning_count }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="model_name" label="模型" width="140" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" width="175">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <div style="display: flex; justify-content: center; gap: 4px; white-space: nowrap;">
              <el-button text type="primary" size="small" @click="$router.push(`/reviews/${row.id}`)">
                详情
              </el-button>
              <el-button
                v-if="row.status === 'failed'"
                text
                type="warning"
                size="small"
                :loading="retryingIds.has(row.id)"
                @click="handleRetry(row)"
              >
                重试
              </el-button>
              <el-button text type="danger" size="small" @click="handleDelete(row)">
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </div>

    <!-- 按日期删除对话框 -->
    <el-dialog
      v-model="dateRangeDialogVisible"
      title="按日期范围删除评审记录"
      width="500px"
    >
      <el-form :model="dateRangeForm" label-width="100px">
        <el-form-item label="开始日期">
          <el-date-picker
            v-model="dateRangeForm.start_date"
            type="date"
            placeholder="选择开始日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker
            v-model="dateRangeForm.end_date"
            type="date"
            placeholder="选择结束日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="项目（可选）">
          <el-select v-model="dateRangeForm.project_id" placeholder="全部项目" clearable style="width: 100%">
            <el-option
              v-for="p in projectOptions"
              :key="p.id"
              :label="p.name"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dateRangeDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="handleDeleteByDate">确定删除</el-button>
      </template>
    </el-dialog>

    <!-- 手动添加评审对话框 -->
    <el-dialog
      v-model="manualReviewDialogVisible"
      title="手动添加评审"
      width="500px"
      append-to-body
    >
      <el-form
        ref="manualReviewFormRef"
        :model="manualReviewForm"
        :rules="manualReviewRules"
        label-width="100px"
      >
        <el-form-item label="项目" prop="project_id">
          <el-select v-model="manualReviewForm.project_id" placeholder="请选择项目" style="width: 100%">
            <el-option
              v-for="p in projectOptions"
              :key="p.id"
              :label="p.name"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="MR 短 ID" prop="mr_iid">
          <el-input
            v-model="manualReviewForm.mr_iid"
            placeholder="请输入 MR 的短 ID（如：123）"
            clearable
          />
          <div class="form-tip">MR 的 IID（如 !123 后面的数字部分），不是完整 URL</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="manualReviewDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleManualReview">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, Refresh, Search, RefreshRight } from '@element-plus/icons-vue'
import { getReviews, deleteReview, batchDeleteReviews, batchRetryReviews, deleteReviewsByDate, createManualReview, clearAllReviews, retryReview } from '@/api/reviews'
import { getProjects } from '@/api/projects'
import { useTable } from '@/composables/useTable'
import { formatDateTime } from '@/utils/format'
import StatusTag from '@/components/common/StatusTag.vue'

const route = useRoute()
const projectOptions = ref([])

const filters = ref({
  project_id: route.query.project_id || '',
  status: '',
  keyword: ''
})

const { loading, tableData, total, pagination, loadData, handlePageChange, handleSizeChange } = useTable(getReviews)

const filteredData = computed(() => {
  let data = tableData.value
  if (filters.value.keyword) {
    data = data.filter((r) => r.mr_title?.includes(filters.value.keyword))
  }
  return data
})

// 批量选择
const selectedRows = ref([])
const selectedIds = ref([])
const retryingIds = ref(new Set())

function handleSelectionChange(selection) {
  selectedRows.value = selection
  selectedIds.value = selection.map(row => row.id)
}

// 重试
async function handleRetry(row) {
  try {
    retryingIds.value.add(row.id)
    await retryReview(row.id)
    ElMessage.success('已重新提交评审任务')
    loadData(filters.value)
  } catch (error) {
    ElMessage.error(error.message || '重试失败')
  } finally {
    retryingIds.value.delete(row.id)
  }
}

// 单条删除
async function handleDelete(row) {
  try {
    const title = row.mr_title || `MR #${row.mr_iid}`
    await ElMessageBox.confirm(
      `确定要删除评审记录 "${title}" 吗？`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    await deleteReview(row.id)
    ElMessage.success('删除成功')
    loadData(filters.value)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除失败')
    }
  }
}

// 清空所有
async function handleClearAll() {
  try {
    await ElMessageBox.confirm(
      '确定要清空所有评审记录吗？此操作不可恢复！',
      '清空确认',
      {
        confirmButtonText: '确定清空',
        cancelButtonText: '取消',
        type: 'error',
        dangerouslyUseHTMLString: true
      }
    )
    await ElMessageBox.confirm(
      '<b>再次确认</b>：这将删除所有评审记录和评论，清空 Redis 缓存',
      '最终确认',
      {
        confirmButtonText: '我确定',
        cancelButtonText: '取消',
        type: 'error',
        dangerouslyUseHTMLString: true
      }
    )
    await clearAllReviews()
    ElMessage.success('已清空所有评审记录')
    selectedIds.value = []
    loadData(filters.value)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '清空失败')
    }
  }
}

// 批量删除
async function handleBatchDelete() {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请先选择要删除的记录')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedIds.value.length} 条评审记录吗？`,
      '批量删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    await batchDeleteReviews(selectedIds.value)
    ElMessage.success('批量删除成功')
    selectedIds.value = []
    loadData(filters.value)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '批量删除失败')
    }
  }
}

// 批量重试
async function handleBatchRetry() {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请先选择要重试的记录')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定要重试选中的 ${selectedIds.value.length} 条评审记录吗？`,
      '批量重试确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    const result = await batchRetryReviews(selectedIds.value)
    ElMessage.success(`已提交 ${result.retried} 条重试任务`)
    selectedIds.value = []
    loadData(filters.value)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '批量重试失败')
    }
  }
}

// 按日期范围删除
const dateRangeDialogVisible = ref(false)
const dateRangeForm = ref({
  start_date: '',
  end_date: '',
  project_id: ''
})

function openDateRangeDialog() {
  dateRangeForm.value = {
    start_date: '',
    end_date: '',
    project_id: filters.value.project_id || ''
  }
  dateRangeDialogVisible.value = true
}

async function handleDeleteByDate() {
  if (!dateRangeForm.value.start_date || !dateRangeForm.value.end_date) {
    ElMessage.warning('请选择开始和结束日期')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定要删除 ${dateRangeForm.value.start_date} 至 ${dateRangeForm.value.end_date} 之间的评审记录吗？`,
      '按日期删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    await deleteReviewsByDate(
      dateRangeForm.value.start_date,
      dateRangeForm.value.end_date,
      dateRangeForm.value.project_id || null
    )
    ElMessage.success('删除成功')
    dateRangeDialogVisible.value = false
    loadData(filters.value)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除失败')
    }
  }
}

// 手动添加评审
const manualReviewDialogVisible = ref(false)
const manualReviewForm = ref({
  project_id: '',
  mr_iid: ''
})
const manualReviewFormRef = ref(null)
const manualReviewRules = {
  project_id: [{ required: true, message: '请选择项目', trigger: 'change' }],
  mr_iid: [{ required: true, message: '请输入 MR 短 ID', trigger: 'blur' }]
}

function openManualReviewDialog() {
  manualReviewForm.value = {
    project_id: filters.value.project_id || '',
    mr_iid: ''
  }
  manualReviewDialogVisible.value = true
}

async function handleManualReview() {
  try {
    await manualReviewFormRef.value.validate()
    await createManualReview(manualReviewForm.value)
    ElMessage.success('评审任务已创建')
    manualReviewDialogVisible.value = false
    loadData(filters.value)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '创建失败')
    }
  }
}

function resetFilters() {
  filters.value = { project_id: '', status: '', keyword: '' }
  loadData({})
}

onMounted(async () => {
  // 加载项目下拉选项
  try {
    const res = await getProjects()
    projectOptions.value = Array.isArray(res) ? res : []
  } catch { /* ignore */ }
  loadData(filters.value)
})
</script>

<style lang="scss" scoped>
.link-text {
  color: $primary-color;
  cursor: pointer;
  &:hover { text-decoration: underline; }
}

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

.text-danger { color: $danger-color; font-weight: 600; }
.text-warning { color: $warning-color; font-weight: 600; }

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.5;
}
</style>
