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
            <el-option
              v-for="item in platformOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.enabled" placeholder="全部" clearable style="width: 120px">
            <el-option
              v-for="item in enabledOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
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
        <div style="display: flex; gap: 8px; margin-left: auto;">
          <el-button
            type="success"
            :disabled="selectedIds.length === 0"
            @click="handleBatchAction('enable')"
          >
            批量启用 ({{ selectedIds.length }})
          </el-button>
          <el-button
            type="warning"
            :disabled="selectedIds.length === 0"
            @click="handleBatchAction('disable')"
          >
            批量禁用 ({{ selectedIds.length }})
          </el-button>
          <el-button
            type="danger"
            :disabled="selectedIds.length === 0"
            @click="handleBatchAction('delete')"
          >
            批量删除 ({{ selectedIds.length }})
          </el-button>
          <el-button type="primary" @click="openForm()">
            <el-icon><Plus /></el-icon> 新增项目
          </el-button>
        </div>
      </div>

      <el-table :data="filteredData" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="55" align="center" />
        <el-table-column prop="name" label="项目名称" min-width="250">
          <template #default="{ row }">
            <span class="link-text" @click="viewProject(row)">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="platform" label="平台" min-width="100">
          <template #default="{ row }">
            <el-tag :color="platformColors[row.platform]" effect="dark" size="small" style="border: none">
              {{ platformNames[row.platform] || row.platform }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="platform_project_id" label="平台项目 ID" min-width="250" show-overflow-tooltip />
        <el-table-column prop="enabled" label="状态" min-width="200" align="center">
          <template #default="{ row }">
            <el-switch
              :model-value="row.enabled === 1"
              @change="(val) => toggleEnabled(row, val)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="200">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <div class="action-btns">
              <el-button text type="primary" size="small" @click="openForm(row)">
                <el-icon><Edit /></el-icon> 编辑
              </el-button>
              <el-dropdown trigger="click" @command="(cmd) => handleActionCmd(cmd, row)">
                <el-button text size="small">
                  <el-icon><Setting /></el-icon> 配置
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="prompt" :icon="Tickets">Prompt 模板</el-dropdown-item>
                    <el-dropdown-item command="llm" :icon="Cpu">LLM 配置</el-dropdown-item>
                    <el-dropdown-item command="notification" :icon="Bell">通知模板</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-button text type="danger" size="small" @click="handleDelete(row)">
                <el-icon><Delete /></el-icon> 删除
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
    <!-- 通知模板绑定弹窗 -->
    <ProjectNotificationBindings
      v-if="notificationBindingsVisible"
      :visible="notificationBindingsVisible"
      :project-id="currentProject?.id"
      :project-name="currentProject?.name || ''"
      @close="notificationBindingsVisible = false"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Edit, Delete, Cpu, Tickets, Bell, Setting } from '@element-plus/icons-vue'
import { getProjects, deleteProject, updateProject, batchProjectAction } from '@/api/projects'
import { useTable } from '@/composables/useTable'
import { formatDateTime, platformColors, platformNames, mapToOptions, enabledOptions } from '@/utils/format'
import ProjectForm from './ProjectForm.vue'
import ProjectLLMBindings from './ProjectLLMBindings.vue'
import ProjectTemplateBindings from './ProjectTemplateBindings.vue'
import ProjectNotificationBindings from './ProjectNotificationBindings.vue'

const router = useRouter()
const platformOptions = mapToOptions(platformNames)
const formVisible = ref(false)
const llmBindingsVisible = ref(false)
const promptBindingsVisible = ref(false)
const notificationBindingsVisible = ref(false)
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

function openNotificationBindings(project) {
  currentProject.value = project
  notificationBindingsVisible.value = true
}

function handleActionCmd(cmd, project) {
  if (cmd === 'prompt') openPromptBindings(project)
  else if (cmd === 'llm') openLLMBindings(project)
  else if (cmd === 'notification') openNotificationBindings(project)
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

// 批量选择
const selectedIds = ref([])

function handleSelectionChange(selection) {
  selectedIds.value = selection.map(row => row.id)
}

async function handleBatchAction(action) {
  if (selectedIds.value.length === 0) return
  const actionLabel = { enable: '启用', disable: '禁用', delete: '删除' }[action]
  try {
    await ElMessageBox.confirm(
      `确定要批量${actionLabel}选中的 ${selectedIds.value.length} 个项目吗？`,
      '批量操作确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await batchProjectAction(selectedIds.value, action)
    ElMessage.success(`已批量${actionLabel} ${selectedIds.value.length} 个项目`)
    selectedIds.value = []
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '操作失败')
    }
  }
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

.action-btns {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-wrap: nowrap;
}
</style>
