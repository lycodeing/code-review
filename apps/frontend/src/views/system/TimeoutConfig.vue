<template>
  <div class="page-container">
    <div class="table-container">
      <div class="table-toolbar">
        <span class="table-title">系统配置</span>
      </div>

      <div v-loading="loading">
        <el-card shadow="hover" class="settings-card">
          <template #header>
            <div class="card-header">
              <el-icon :size="20" color="#409EFF"><Setting /></el-icon>
              <span>系统配置管理</span>
            </div>
          </template>

          <el-tabs v-if="categories.length" v-model="activeCategory" @tab-change="onCategoryChange">
            <el-tab-pane
              v-for="cat in categories"
              :key="cat.key"
              :label="cat.label"
              :name="cat.key"
            />
          </el-tabs>

          <div v-if="currentSettings.length" class="settings-list">
            <template v-for="(item, index) in currentSettings" :key="item.key">
              <!-- agent_profiles：全宽卡片网格 -->
              <div v-if="item.key === 'agent_profiles'" class="setting-item setting-item--full">
                <div class="setting-item__left">
                  <div class="setting-item__icon" :style="{ background: iconGradients[index % iconGradients.length] }">
                    <el-icon :size="18" color="#fff">
                      <component :is="categoryIcons[activeCategory] || Tools" />
                    </el-icon>
                  </div>
                  <div class="setting-item__info">
                    <div class="setting-item__label">{{ item.label }}</div>
                    <div class="setting-item__desc">{{ item.description }}</div>
                  </div>
                </div>
                <div class="agent-section">
                  <div class="agent-grid">
                    <div v-for="(agent, idx) in agentProfiles" :key="idx" class="agent-card">
                      <div class="agent-card__header">
                        <el-tag :type="severityTagType(agent.severity)" effect="dark" round>
                          {{ agent.name || '未命名' }}
                        </el-tag>
                        <el-tag :type="severityTagType(agent.severity)" size="small" round>
                          {{ severityLabel(agent.severity) }}
                        </el-tag>
                        <div class="agent-card__actions">
                          <el-button text size="small" @click="editAgent(idx)">编辑</el-button>
                          <el-button type="danger" text size="small" @click="agentProfiles.splice(idx, 1)">删除</el-button>
                        </div>
                      </div>
                      <div class="agent-card__focus">{{ agent.focus || '暂无关注点描述' }}</div>
                    </div>
                  </div>
                  <el-button type="primary" plain @click="addAgent">
                    <el-icon><Plus /></el-icon>
                    添加 Agent
                  </el-button>
                </div>
              </div>

              <!-- 普通配置项 -->
              <div v-else class="setting-item" :class="{ 'setting-item--last': index === currentSettings.length - 1 }">
                <div class="setting-item__left">
                  <div class="setting-item__icon" :style="{ background: iconGradients[index % iconGradients.length] }">
                    <el-icon :size="18" color="#fff">
                      <component :is="categoryIcons[activeCategory] || Tools" />
                    </el-icon>
                  </div>
                  <div class="setting-item__info">
                    <div class="setting-item__label">{{ item.label }}</div>
                    <div class="setting-item__desc">{{ item.description }}</div>
                  </div>
                </div>
                <div class="setting-item__right">
                  <template v-if="item.input_type === 'number'">
                    <el-input-number
                      v-model="form[item.key]"
                      :min="-1"
                      :step="item.unit === '秒' ? 30 : 1"
                      controls-position="right"
                      style="width: 160px"
                    />
                    <span v-if="item.unit" class="setting-unit">{{ item.unit }}</span>
                    <el-tag v-if="form[item.key] === -1" type="warning" size="small" style="margin-left: 8px">
                      无限制
                    </el-tag>
                  </template>
                  <template v-else-if="item.input_type === 'switch'">
                    <el-switch v-model="form[item.key]" />
                  </template>
                  <template v-else-if="item.input_type === 'select'">
                    <el-select v-model="form[item.key]" style="width: 200px">
                      <el-option v-for="opt in item.options" :key="opt.value" :label="opt.label" :value="opt.value" />
                    </el-select>
                  </template>
                  <template v-else>
                    <el-input v-model="form[item.key]" style="width: 240px" />
                  </template>
                </div>
              </div>
            </template>
          </div>

          <el-empty v-else-if="!loading" description="该分类暂无配置项" />

          <div class="settings-footer">
            <el-button type="primary" :loading="saving" :disabled="!currentSettings.length" @click="handleSave">
              <el-icon><Check /></el-icon>
              保存配置
            </el-button>
            <el-button :disabled="!currentSettings.length" @click="loadCategorySettings">
              <el-icon><RefreshRight /></el-icon>
              重置
            </el-button>
          </div>
        </el-card>
      </div>
    </div>

    <el-dialog v-model="agentEditVisible" :title="agentEditIdx === -1 ? '添加 Agent' : '编辑 Agent'" width="480px" destroy-on-close>
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="agentEditForm.name" placeholder="如 security" />
        </el-form-item>
        <el-form-item label="报告级别">
          <el-select v-model="agentEditForm.severity" style="width: 200px">
            <el-option label="严重 (critical)" value="critical" />
            <el-option label="警告 (warning)" value="warning" />
            <el-option label="建议 (suggestion)" value="suggestion" />
            <el-option label="提示 (info)" value="info" />
          </el-select>
        </el-form-item>
        <el-form-item label="关注点">
          <el-input v-model="agentEditForm.focus" type="textarea" :rows="3" placeholder="描述该 Agent 的评审关注范围" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="agentEditVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmAgentEdit">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Setting, Check, RefreshRight, Clock, Tools, Plus } from '@element-plus/icons-vue'
import {
  getSystemSettingCategories,
  getSystemSettingsByCategory,
  updateSystemSettings,
} from '@/api/systemSettings'

const loading = ref(false)
const saving = ref(false)
const categories = ref([])
const activeCategory = ref('')
const allSettings = reactive({})
const form = reactive({})

const agentProfiles = reactive([])
const agentEditVisible = ref(false)
const agentEditIdx = ref(-1)
const agentEditForm = reactive({ name: '', focus: '', severity: 'warning' })

const severityLabel = s => ({ critical: '严重', warning: '警告', suggestion: '建议', info: '提示' }[s] || s)
const severityTagType = s => ({ critical: 'danger', warning: 'warning', suggestion: '', info: 'info' }[s] || 'info')

function syncAgentProfilesFromForm() {
  try {
    const raw = form.agent_profiles
    const parsed = typeof raw === 'string' ? JSON.parse(raw || '[]') : raw
    agentProfiles.splice(0, agentProfiles.length, ...parsed)
  } catch {
    agentProfiles.splice(0, agentProfiles.length)
  }
}

function addAgent() {
  agentEditIdx.value = -1
  Object.assign(agentEditForm, { name: '', focus: '', severity: 'warning' })
  agentEditVisible.value = true
}

function editAgent(idx) {
  agentEditIdx.value = idx
  Object.assign(agentEditForm, { ...agentProfiles[idx] })
  agentEditVisible.value = true
}

function confirmAgentEdit() {
  if (!agentEditForm.name.trim()) {
    ElMessage.warning('Agent 名称不能为空')
    return
  }
  if (agentEditIdx.value === -1) {
    agentProfiles.push({ ...agentEditForm })
  } else {
    Object.assign(agentProfiles[agentEditIdx.value], { ...agentEditForm })
  }
  form.agent_profiles = JSON.stringify(agentProfiles)
  agentEditVisible.value = false
}

const categoryIcons = { timeout: Clock }
const iconGradients = [
  'linear-gradient(135deg, #409EFF, #79bbff)',
  'linear-gradient(135deg, #67C23A, #95d475)',
  'linear-gradient(135deg, #E6A23C, #eebe77)',
  'linear-gradient(135deg, #F56C6C, #f89898)',
  'linear-gradient(135deg, #909399, #b1b3b8)',
]

const currentSettings = computed(() => allSettings[activeCategory.value] || [])

function parseFormValue(item) {
  if (item.input_type === 'number') return parseInt(item.value, 10) || 0
  if (item.input_type === 'switch') return item.value === 'true' || item.value === '1'
  return item.value
}

function serializeFormValue(key) {
  const item = currentSettings.value.find(s => s.key === key)
  if (!item) return ''
  if (item.input_type === 'switch') return form[key] ? 'true' : 'false'
  return String(form[key])
}

async function loadCategories() {
  try {
    const data = await getSystemSettingCategories()
    categories.value = data
    if (data.length && !activeCategory.value) {
      activeCategory.value = data[0].key
    }
  } catch {
    ElMessage.error('加载配置分类失败')
  }
}

async function loadCategorySettings() {
  if (!activeCategory.value) return
  loading.value = true
  try {
    const data = await getSystemSettingsByCategory(activeCategory.value)
    allSettings[activeCategory.value] = data
    for (const item of data) {
      form[item.key] = parseFormValue(item)
    }
    if (data.some(s => s.key === 'agent_profiles')) {
      syncAgentProfilesFromForm()
    }
  } catch {
    ElMessage.error('加载配置失败')
  } finally {
    loading.value = false
  }
}

function onCategoryChange() {
  loadCategorySettings()
}

async function handleSave() {
  if (form.agent_profiles !== undefined) {
    form.agent_profiles = JSON.stringify(agentProfiles)
  }

  const items = currentSettings.value.map(item => ({
    key: item.key,
    value: serializeFormValue(item.key),
  }))

  for (const item of items) {
    const setting = currentSettings.value.find(s => s.key === item.key)
    if (setting?.input_type === 'number') {
      const val = parseInt(item.value, 10)
      if (isNaN(val) || (val !== -1 && val <= 0)) {
        ElMessage.warning(`${setting.label}：请输入 -1（无限制）或正整数`)
        return
      }
    }
  }

  saving.value = true
  try {
    const data = await updateSystemSettings({ settings: items })
    allSettings[activeCategory.value] = data.filter(s => s.category === activeCategory.value)
    for (const item of allSettings[activeCategory.value]) {
      form[item.key] = parseFormValue(item)
    }
    ElMessage.success('配置已保存')
  } catch {
    ElMessage.error('保存配置失败')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadCategories()
  if (activeCategory.value) {
    await loadCategorySettings()
  }
})
</script>

<style lang="scss" scoped>
.settings-card {
  :deep(.el-card__header) {
    padding: 16px 24px;
    border-bottom: 1px solid #f0f0f0;
  }

  :deep(.el-card__body) {
    padding: 0;
  }

  :deep(.el-tabs) {
    padding: 0 24px;
  }

  :deep(.el-tabs__header) {
    margin-bottom: 0;
  }
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.settings-list {
  padding: 8px 24px;
}

.setting-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 0;
  border-bottom: 1px solid #f5f5f5;

  &--last {
    border-bottom: none;
  }

  &--full {
    flex-wrap: wrap;
    border-bottom: none;
    padding-bottom: 0;
  }
}

.setting-item__left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}

.setting-item--full .setting-item__left {
  width: auto;
}

.setting-item__icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.setting-item__info {
  min-width: 0;
}

.setting-item__label {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
}

.setting-item__desc {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}

.setting-item__right {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  margin-left: 24px;
}

.setting-unit {
  margin-left: 8px;
  color: #606266;
  font-size: 14px;
}

.settings-footer {
  padding: 16px 24px;
  border-top: 1px solid #f0f0f0;
  display: flex;
  gap: 12px;
}

// Agent 卡片网格
.agent-section {
  width: 100%;
  margin-top: 16px;
  padding-bottom: 8px;
}

.agent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.agent-card {
  background: #f7f8fa;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  padding: 14px 16px;
  transition: all 0.2s;

  &:hover {
    border-color: #d0d3d9;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  }
}

.agent-card__header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.agent-card__actions {
  margin-left: auto;
  display: flex;
  gap: 0;
}

.agent-card__focus {
  font-size: 12px;
  color: #909399;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
