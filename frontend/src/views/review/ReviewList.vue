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
        <el-button @click="loadData(filters)">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>

      <el-table :data="filteredData" v-loading="loading" stripe>
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
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="$router.push(`/reviews/${row.id}`)">
              详情
            </el-button>
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getReviews } from '@/api/review'
import { getProjects } from '@/api/project'
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

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.text-danger { color: $danger-color; font-weight: 600; }
.text-warning { color: $warning-color; font-weight: 600; }
</style>
