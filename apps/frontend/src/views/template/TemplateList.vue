<template>
  <div class="page-container">
    <!-- 搜索栏 -->
    <div class="filter-container">
      <el-form :model="filters" inline>
        <el-form-item label="名称">
          <el-input v-model="filters.keyword" placeholder="搜索模板名称" clearable style="width: 200px" />
        </el-form-item>
        <el-form-item label="类别">
          <el-select v-model="filters.category" placeholder="全部" clearable style="width: 130px">
            <el-option
              v-for="item in templateCategoryOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="语言">
          <el-select v-model="filters.locale" placeholder="全部" clearable style="width: 120px">
            <el-option
              v-for="item in templateLanguageOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData(buildParams())">
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
        <span class="table-title">Prompt 模板列表</span>
        <el-button type="primary" @click="openForm()">
          <el-icon><Plus /></el-icon> 新增模板
        </el-button>
      </div>

      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="name" label="模板名称" min-width="180" />
        <el-table-column prop="category" label="类别" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ row.category || 'default' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="locale" label="语言" width="80" align="center">
          <template #default="{ row }">
            {{ row.locale === 'zh' ? '中文' : 'English' }}
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
              {{ row.enabled ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="模板内容" min-width="200" show-overflow-tooltip />
        <el-table-column prop="updated_at" label="更新时间" width="175">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="openForm(row)">编辑</el-button>
            <el-button text type="danger" size="small" @click="handleDelete(row)">删除</el-button>
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
          @current-change="(p) => { pagination.page = p; loadData(buildParams()) }"
          @size-change="(s) => { pagination.pageSize = s; pagination.page = 1; loadData(buildParams()) }"
        />
      </div>
    </div>

    <!-- 新增/编辑弹窗 -->
    <TemplateForm
      v-if="formVisible"
      :visible="formVisible"
      :template="currentTemplate"
      @close="formVisible = false"
      @saved="onSaved"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTemplates, deleteTemplate } from '@/api/templates'
import { useTable } from '@/composables/useTable'
import { formatDateTime, templateCategoryOptions, templateLanguageOptions } from '@/utils/format'
import TemplateForm from './TemplateForm.vue'

const formVisible = ref(false)
const currentTemplate = ref(null)
const filters = ref({ keyword: '', category: '', locale: '' })

const { loading, tableData, total, pagination, loadData } = useTable(getTemplates, 50)

function buildParams() {
  return {
    category: filters.value.category || undefined,
    locale: filters.value.locale || undefined
  }
}

function resetFilters() {
  filters.value = { keyword: '', category: '', locale: '' }
  loadData({})
}

function openForm(template = null) {
  currentTemplate.value = template
  formVisible.value = true
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定要删除模板「${row.name}」吗？`, '删除确认', {
    type: 'warning'
  })
  try {
    await deleteTemplate(row.id)
    ElMessage.success('删除成功')
    loadData(buildParams())
  } catch { /* 已处理 */ }
}

function onSaved() {
  formVisible.value = false
  loadData(buildParams())
}

loadData(buildParams())
</script>

<style lang="scss" scoped>
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
</style>
