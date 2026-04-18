<template>
  <div class="page-container">
    <!-- 搜索栏 -->
    <div class="filter-container">
      <el-form :model="filters" inline>
        <el-form-item label="项目名称">
          <el-input v-model="filters.keyword" placeholder="搜索项目名称" clearable style="width: 200px" />
        </el-form-item>
        <el-form-item label="平台">
          <el-select v-model="filters.platform" placeholder="全部" clearable style="width: 140px">
            <el-option label="GitHub" value="github" />
            <el-option label="GitLab" value="gitlab" />
            <el-option label="Gitee" value="gitee" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.enabled" placeholder="全部" clearable style="width: 120px">
            <el-option label="启用" :value="1" />
            <el-option label="禁用" :value="0" />
          </el-select>
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
        <span class="table-title">项目列表</span>
        <el-button type="primary" @click="openForm()">
          <el-icon><Plus /></el-icon> 新增项目
        </el-button>
      </div>

      <el-table :data="filteredData" v-loading="loading" stripe>
        <el-table-column prop="name" label="项目名称" min-width="130">
          <template #default="{ row }">
            <span class="link-text" @click="viewProject(row)">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="platform" label="平台" width="140">
          <template #default="{ row }">
            <el-tag :color="platformColors[row.platform]" effect="dark" size="small" style="border: none">
              {{ platformNames[row.platform] || row.platform }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="platform_project_id" label="平台项目 ID" min-width="160" show-overflow-tooltip />
        <el-table-column prop="enabled" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-switch
              :model-value="row.enabled === 1"
              @change="(val) => toggleEnabled(row, val)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="240">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="openForm(row)">
              <el-icon><Edit /></el-icon> 编辑
            </el-button>
            <el-button text size="small" class="prompt-btn" @click="openPromptBindings(row)">
              <el-icon><Tickets /></el-icon> 模板
            </el-button>
            <el-button text size="small" class="llm-btn" @click="openLLMBindings(row)">
              <el-icon><Cpu /></el-icon> LLM
            </el-button>
            <el-button text type="danger" size="small" @click="handleDelete(row)">
              <el-icon><Delete /></el-icon> 删除
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

    <!-- 新增/编辑表单弹窗 -->
    <ProjectForm
      v-if="formVisible"
      :visible="formVisible"
      :project="currentProject"
      @close="formVisible = false"
      @saved="onSaved"
    />

    <!-- LLM 绑定管理弹窗 -->
    <ProjectLLMBindings
      v-if="llmBindingsVisible"
      :visible="llmBindingsVisible"
      :project-id="currentProject?.id"
      :project-name="currentProject?.name || ''"
      @close="llmBindingsVisible = false"
    />

    <!-- Prompt 模板绑定管理弹窗 -->
    <ProjectTemplateBindings
      v-if="promptBindingsVisible"
      :visible="promptBindingsVisible"
      :project-id="currentProject?.id"
      :project-name="currentProject?.name || ''"
      @close="promptBindingsVisible = false"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Edit, Delete, Cpu, Tickets } from '@element-plus/icons-vue'
import { getProjects, deleteProject, updateProject } from '@/api/project'
import { useTable } from '@/composables/useTable'
import { formatDateTime, platformColors, platformNames } from '@/utils/format'
import ProjectForm from './ProjectForm.vue'
import ProjectLLMBindings from './ProjectLLMBindings.vue'
import ProjectTemplateBindings from './ProjectTemplateBindings.vue'

const router = useRouter()
const formVisible = ref(false)
const llmBindingsVisible = ref(false)
const promptBindingsVisible = ref(false)
const currentProject = ref(null)

const filters = ref({ keyword: '', platform: '', enabled: '' })

const { loading, tableData, total, pagination, loadData, handlePageChange, handleSizeChange } = useTable(getProjects)

// 前端搜索过滤
const filteredData = computed(() => {
  let data = tableData.value
  const { keyword, platform, enabled } = filters.value
  if (keyword) {
    data = data.filter((r) => r.name?.includes(keyword))
  }
  if (platform) {
    data = data.filter((r) => r.platform === platform)
  }
  if (enabled !== '' && enabled !== null) {
    data = data.filter((r) => r.enabled === enabled)
  }
  return data
})

function resetFilters() {
  filters.value = { keyword: '', platform: '', enabled: '' }
}

function openForm(project = null) {
  currentProject.value = project
  formVisible.value = true
}

function openLLMBindings(project) {
  currentProject.value = project
  llmBindingsVisible.value = true
}

function openPromptBindings(project) {
  currentProject.value = project
  promptBindingsVisible.value = true
}

function viewProject(row) {
  // 跳转到该项目下的评审记录
  router.push({ path: '/reviews', query: { project_id: row.id } })
}

async function toggleEnabled(row, val) {
  try {
    await updateProject(row.id, { enabled: val ? 1 : 0 })
    row.enabled = val ? 1 : 0
    ElMessage.success(val ? '已启用' : '已禁用')
  } catch {
    // 错误已由拦截器处理
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定要删除项目「${row.name}」吗？`, '删除确认', {
    type: 'warning',
    confirmButtonText: '确定',
    cancelButtonText: '取消'
  })
  try {
    await deleteProject(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch {
    // 错误已由拦截器处理
  }
}

function onSaved() {
  formVisible.value = false
  loadData()
}

// 初始化加载
loadData()
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

.llm-btn {
  color: #6366f1;
  &:hover { color: #4f46e5; }
}

.prompt-btn {
  color: #e6a23c;
  &:hover { color: #cf8a22; }
}
</style>
