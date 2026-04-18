<template>
  <el-dialog
    :model-value="visible"
    :title="`LLM 配置绑定 — ${projectName}`"
    width="800px"
    destroy-on-close
    @close="emit('close')"
  >
    <!-- 工具栏 -->
    <div class="binding-toolbar">
      <el-button type="primary" @click="openAddDialog">
        <el-icon><Plus /></el-icon> 添加绑定
      </el-button>
    </div>

    <!-- 绑定列表 -->
    <el-table
      :data="bindings"
      v-loading="loading"
      stripe
      max-height="380"
      class="binding-table"
    >
      <el-table-column label="LLM 配置" min-width="200">
        <template #default="{ row }">
          <div class="config-cell">
            <el-tag
              :color="providerColors[row.llm_config?.provider] || ''"
              effect="dark"
              size="small"
              style="border: none"
            >
              {{ providerNames[row.llm_config?.provider] || '-' }}
            </el-tag>
            <span class="config-name">{{ row.llm_config?.name || '-' }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="模型" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">
          <span>{{ row.llm_config?.model_name || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="priority" label="优先级" width="80" align="center" />
      <el-table-column label="默认" width="70" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.is_default" type="success" size="small" effect="plain">默认</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-switch :model-value="row.enabled" @change="(val) => toggleEnabled(row, val)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right" align="center">
        <template #default="{ row }">
          <div class="action-cell">
            <el-button
              v-if="!row.is_default"
              text
              type="primary"
              size="small"
              @click="handleSetDefault(row)"
            >
              <el-icon><Star /></el-icon> 默认
            </el-button>
            <el-dropdown trigger="click" @command="(cmd) => handleAction(cmd, row)">
              <el-button text size="small" class="more-btn">
                <el-icon><MoreFilled /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="edit" :icon="Edit">编辑</el-dropdown-item>
                  <el-dropdown-item command="delete" :icon="Delete" divided>
                    <span style="color: #f56c6c">删除</span>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && !bindings.length" description="暂无绑定配置，点击上方按钮添加" />

    <template #footer>
      <el-button @click="emit('close')">关闭</el-button>
    </template>
  </el-dialog>

  <!-- 添加/编辑绑定对话框 -->
  <el-dialog
    v-model="addDialogVisible"
    :title="editingBinding ? '编辑绑定' : '添加绑定'"
    width="480px"
    destroy-on-close
    append-to-body
  >
    <el-form ref="bindingFormRef" :model="bindingForm" :rules="bindingRules" label-width="100px">
      <el-form-item label="LLM 配置" prop="llm_config_id">
        <el-select
          v-model="bindingForm.llm_config_id"
          placeholder="选择 LLM 配置"
          style="width: 100%"
          :disabled="editingBinding !== null"
          filterable
        >
          <el-option
            v-for="config in availableConfigs"
            :key="config.id"
            :label="`${config.name} (${providerNames[config.provider] || config.provider} / ${config.model_name})`"
            :value="config.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="优先级" prop="priority">
        <el-input-number v-model="bindingForm.priority" :min="0" :max="100" style="width: 100%" />
        <div class="form-tip">数值越大优先级越高，优先使用高优先级配置</div>
      </el-form-item>

      <el-form-item label="设为默认">
        <el-switch v-model="bindingForm.is_default" />
        <div class="form-tip">默认配置在评审时优先使用</div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="addDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSaveBinding">
        {{ editingBinding ? '保存' : '添加' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Star, MoreFilled, Edit, Delete } from '@element-plus/icons-vue'
import {
  getLLMConfigs,
  getProjectLLMBindings,
  createProjectLLMBinding,
  updateProjectLLMBinding,
  deleteProjectLLMBinding,
  setDefaultLLMBinding
} from '@/api/llm'

const props = defineProps({
  visible: Boolean,
  projectId: { type: String, required: true },
  projectName: { type: String, default: '' }
})
const emit = defineEmits(['close'])

const loading = ref(false)
const bindings = ref([])
const availableConfigs = ref([])
const addDialogVisible = ref(false)
const editingBinding = ref(null)
const submitting = ref(false)

const bindingFormRef = ref(null)
const bindingForm = reactive({
  llm_config_id: '',
  is_default: false,
  priority: 0
})

const bindingRules = {
  llm_config_id: [{ required: true, message: '请选择 LLM 配置', trigger: 'change' }],
  priority: [{ required: true, message: '请输入优先级', trigger: 'blur' }]
}

const providerColors = {
  openai: '#10a37f',
  anthropic: '#d4a574',
  deepseek: '#6366f1',
  ollama: '#000000',
  azure: '#0078d4',
  bedrock: '#232f3e',
  dashscope: '#ff6a00',
  zhipu: '#3b5cff'
}

const providerNames = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  deepseek: 'DeepSeek',
  ollama: 'Ollama',
  azure: 'Azure',
  bedrock: 'AWS Bedrock',
  dashscope: '阿里云',
  zhipu: '智谱 AI'
}

/** 加载绑定列表和可用 LLM 配置 */
async function loadData() {
  if (!props.projectId) return

  loading.value = true
  try {
    const [bindingsRes, configsRes] = await Promise.all([
      getProjectLLMBindings(props.projectId),
      getLLMConfigs(false)
    ])

    bindings.value = Array.isArray(bindingsRes) ? bindingsRes : []
    availableConfigs.value = Array.isArray(configsRes) ? configsRes : []
  } catch (err) {
    ElMessage.error('加载数据失败: ' + (err.message || '未知错误'))
    bindings.value = []
    availableConfigs.value = []
  } finally {
    loading.value = false
  }
}

/** 打开添加绑定弹窗 */
async function openAddDialog() {
  if (availableConfigs.value.length === 0) {
    ElMessage.warning('暂无可用的 LLM 配置，请先在「LLM 配置」页面创建')
    return
  }

  editingBinding.value = null
  Object.assign(bindingForm, { llm_config_id: '', is_default: false, priority: 0 })
  addDialogVisible.value = true
}

/** 下拉菜单操作分发 */
function handleAction(command, row) {
  if (command === 'edit') handleEdit(row)
  else if (command === 'delete') handleDelete(row)
}

/** 打开编辑绑定弹窗 */
function handleEdit(row) {
  editingBinding.value = row
  Object.assign(bindingForm, {
    llm_config_id: row.llm_config_id,
    is_default: row.is_default,
    priority: row.priority
  })
  addDialogVisible.value = true
}

/** 保存绑定（新增/编辑） */
async function handleSaveBinding() {
  const valid = await bindingFormRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (editingBinding.value) {
      await updateProjectLLMBinding(props.projectId, editingBinding.value.id, bindingForm)
      ElMessage.success('更新成功')
    } else {
      await createProjectLLMBinding(props.projectId, bindingForm)
      ElMessage.success('添加成功')
    }
    addDialogVisible.value = false
    loadData()
  } catch (err) {
    ElMessage.error(err.message || '操作失败')
  } finally {
    submitting.value = false
  }
}

/** 设为默认绑定 */
async function handleSetDefault(row) {
  try {
    await setDefaultLLMBinding(props.projectId, row.id)
    ElMessage.success('已设为默认')
    loadData()
  } catch (err) {
    ElMessage.error(err.message || '操作失败')
  }
}

/** 切换绑定启用/禁用 */
async function toggleEnabled(row, val) {
  try {
    await updateProjectLLMBinding(props.projectId, row.id, { enabled: val })
    row.enabled = val
    ElMessage.success(val ? '已启用' : '已禁用')
  } catch (err) {
    ElMessage.error(err.message || '操作失败')
  }
}

/** 删除绑定 */
async function handleDelete(row) {
  const configName = row.llm_config?.name || row.llm_config_id
  await ElMessageBox.confirm(
    `确定要删除「${configName}」绑定吗？`,
    '删除确认',
    { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
  )
  try {
    await deleteProjectLLMBinding(props.projectId, row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (err) {
    ElMessage.error(err.message || '删除失败')
  }
}

/** 弹窗打开时加载数据 */
watch(() => props.visible, (val) => {
  if (val && props.projectId) {
    loadData()
  }
}, { immediate: true })
</script>

<style lang="scss" scoped>
.binding-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.binding-table {
  width: 100%;
}

.config-cell {
  display: flex;
  align-items: center;
  gap: 8px;

  .config-name {
    font-weight: 500;
    color: #303133;
  }
}

.action-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.more-btn {
  padding: 4px 8px;
  color: #606266;
  &:hover { color: #409eff; }
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.4;
}
</style>
