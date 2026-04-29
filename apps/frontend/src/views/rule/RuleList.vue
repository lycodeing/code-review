<template>
  <div class="page-container">
    <!-- 工具栏 -->
    <div class="table-container">
      <div class="table-toolbar">
        <span class="table-title">评审规则列表</span>
        <div>
          <el-button @click="openTemplateDialog">
            <el-icon><Download /></el-icon> 从模板导入
          </el-button>
          <el-button type="primary" @click="openForm()">
            <el-icon><Plus /></el-icon> 新增规则
          </el-button>
        </div>
      </div>

      <el-table :data="rules" v-loading="loading" stripe>
        <el-table-column prop="name" label="规则名称" min-width="180" />
        <el-table-column prop="description" label="描述" min-width="160" show-overflow-tooltip />
        <el-table-column prop="severity" label="严重程度" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="severityType(row.severity)" size="small">{{ row.severity }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="file_pattern" label="文件匹配" width="130" show-overflow-tooltip />
        <el-table-column prop="pattern" label="正则模式" min-width="180" show-overflow-tooltip />
        <el-table-column prop="enabled" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
              {{ row.enabled ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="openForm(row)">编辑</el-button>
            <el-button text type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="formVisible"
      :title="currentRule ? '编辑规则' : '新增规则'"
      width="600px"
      @close="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px">
        <el-form-item label="规则名称" prop="name">
          <el-input v-model="form.name" :disabled="!!currentRule" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="正则模式" prop="pattern">
          <el-input v-model="form.pattern" />
        </el-form-item>
        <el-form-item label="文件匹配" prop="file_pattern">
          <el-input v-model="form.file_pattern" placeholder="**" />
        </el-form-item>
        <el-form-item label="严重程度" prop="severity">
          <el-select v-model="form.severity" style="width: 100%">
            <el-option label="critical" value="critical" />
            <el-option label="warning" value="warning" />
            <el-option label="suggestion" value="suggestion" />
            <el-option label="info" value="info" />
          </el-select>
        </el-form-item>
        <el-form-item label="提示信息" prop="message">
          <el-input v-model="form.message" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 模板导入弹窗 -->
    <el-dialog v-model="templateDialogVisible" title="从模板导入规则" width="800px">
      <el-table
        ref="templateTableRef"
        :data="templates"
        v-loading="templatesLoading"
        stripe
        @selection-change="selectedTemplates = $event"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="name" label="规则名称" min-width="180" />
        <el-table-column prop="description" label="描述" min-width="160" show-overflow-tooltip />
        <el-table-column prop="severity" label="严重程度" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="severityType(row.severity)" size="small">{{ row.severity }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="file_pattern" label="文件匹配" width="120" show-overflow-tooltip />
        <el-table-column prop="pattern" label="正则模式" min-width="160" show-overflow-tooltip />
      </el-table>
      <template #footer>
        <el-button @click="templateDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="importing"
          :disabled="!selectedTemplates.length"
          @click="handleImport"
        >
          导入选中（{{ selectedTemplates.length }}）
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getRules, createRule, updateRule, deleteRule, getTemplates, importTemplates } from '@/api/reviewRules'

// ——— 规则列表 ———
const loading = ref(false)
const rules = ref([])

async function loadRules() {
  loading.value = true
  try {
    rules.value = await getRules()
  } finally {
    loading.value = false
  }
}

// ——— 新增/编辑表单 ———
const formVisible = ref(false)
const saving = ref(false)
const currentRule = ref(null)
const formRef = ref(null)
const form = ref(defaultForm())

const formRules = {
  name: [{ required: true, message: '请输入规则名称', trigger: 'blur' }],
  pattern: [{ required: true, message: '请输入正则模式', trigger: 'blur' }],
  message: [{ required: true, message: '请输入提示信息', trigger: 'blur' }],
}

function defaultForm() {
  return { name: '', description: '', pattern: '', severity: 'warning', message: '', file_pattern: '**', enabled: true }
}

function openForm(rule = null) {
  currentRule.value = rule
  form.value = rule
    ? { name: rule.name, description: rule.description, pattern: rule.pattern, severity: rule.severity, message: rule.message, file_pattern: rule.file_pattern, enabled: rule.enabled }
    : defaultForm()
  formVisible.value = true
}

function resetForm() {
  formRef.value?.resetFields()
  currentRule.value = null
}

async function handleSave() {
  await formRef.value?.validate()
  saving.value = true
  try {
    if (currentRule.value) {
      await updateRule(currentRule.value.id, form.value)
    } else {
      await createRule(form.value)
    }
    ElMessage.success('保存成功')
    formVisible.value = false
    loadRules()
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定要删除规则「${row.name}」吗？`, '删除确认', { type: 'warning' })
  try {
    await deleteRule(row.id)
    ElMessage.success('删除成功')
    loadRules()
  } catch { /* 已处理 */ }
}

// ——— 模板导入 ———
const templateDialogVisible = ref(false)
const templatesLoading = ref(false)
const templates = ref([])
const selectedTemplates = ref([])
const importing = ref(false)

async function openTemplateDialog() {
  templateDialogVisible.value = true
  selectedTemplates.value = []
  templatesLoading.value = true
  try {
    templates.value = await getTemplates()
  } finally {
    templatesLoading.value = false
  }
}

async function handleImport() {
  importing.value = true
  try {
    const ids = selectedTemplates.value.map((r) => r.id)
    await importTemplates(ids)
    ElMessage.success(`成功导入 ${ids.length} 条规则`)
    templateDialogVisible.value = false
    loadRules()
  } finally {
    importing.value = false
  }
}

// ——— 工具函数 ———
function severityType(severity) {
  return { critical: 'danger', warning: 'warning', suggestion: 'primary', info: 'info' }[severity] ?? 'info'
}

loadRules()
</script>

<style lang="scss" scoped>
.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.table-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}
</style>
