<template>
  <div class="page-container">
    <div class="table-container">
      <div class="table-toolbar">
        <span class="table-title">系统配置</span>
      </div>

      <div v-loading="loading" class="settings-wrapper">
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
            <div
              v-for="(item, index) in currentSettings"
              :key="item.key"
              class="setting-item"
              :class="{ 'setting-item--last': index === currentSettings.length - 1 }"
            >
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
                <!-- number 类型 -->
                <template v-if="item.input_type === 'number'">
                  <el-input-number
                    v-model="form[item.key]"
                    :min="-1"
                    :step="item.unit === '秒' ? 30 : 1"
                    controls-position="right"
                    style="width: 160px"
                  />
                  <span v-if="item.unit" class="setting-unit">{{ item.unit }}</span>
                  <el-tag
                    v-if="form[item.key] === -1"
                    type="warning"
                    size="small"
                    style="margin-left: 8px"
                  >
                    无限制
                  </el-tag>
                </template>

                <!-- switch 类型 -->
                <template v-else-if="item.input_type === 'switch'">
                  <el-switch v-model="form[item.key]" />
                </template>

                <!-- select 类型 -->
                <template v-else-if="item.input_type === 'select'">
                  <el-select v-model="form[item.key]" style="width: 200px">
                    <el-option
                      v-for="opt in item.options"
                      :key="opt.value"
                      :label="opt.label"
                      :value="opt.value"
                    />
                  </el-select>
                </template>

                <!-- text 类型（默认） -->
                <template v-else>
                  <el-input v-model="form[item.key]" style="width: 240px" />
                </template>
              </div>
            </div>
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
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Setting, Check, RefreshRight, Clock, Timer, Tools } from '@element-plus/icons-vue'
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
  const items = currentSettings.value.map(item => ({
    key: item.key,
    value: serializeFormValue(item.key),
  }))

  // 校验 number 类型
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
    // 只刷新当前分类
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
.settings-wrapper {
  max-width: 860px;
}

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
}

.setting-item__left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
  min-width: 0;
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
  max-width: 360px;
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
</style>
