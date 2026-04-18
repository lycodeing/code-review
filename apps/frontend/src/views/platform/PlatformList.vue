<template>
  <div class="page-container">
    <div class="table-container">
      <div class="table-toolbar">
        <span class="table-title">平台配置</span>
        <el-button type="primary" @click="openForm()">
          <el-icon><Plus /></el-icon> 新增平台
        </el-button>
      </div>

      <!-- 平台卡片展示 -->
      <el-row :gutter="16" v-loading="loading">
        <el-col :xs="24" :sm="12" :lg="8" v-for="item in platforms" :key="item.platform">
          <div class="platform-card">
            <div class="platform-header">
              <div class="platform-info">
                <el-tag
                  :color="platformColors[item.platform]"
                  effect="dark"
                  size="large"
                  style="border: none"
                >
                  {{ platformNames[item.platform] || item.platform }}
                </el-tag>
                <el-switch
                  :model-value="item.enabled"
                  @change="(val) => toggleEnabled(item, val)"
                  style="margin-left: auto"
                />
              </div>
              <p v-if="item.description" class="platform-desc">{{ item.description }}</p>
            </div>

            <div class="platform-body">
              <div class="info-row">
                <span class="info-label">API 地址</span>
                <span class="info-value">{{ item.api_url || '-' }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">Access Token</span>
                <span class="info-value">{{ item.access_token || '-' }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">Webhook Secret</span>
                <span class="info-value">{{ item.webhook_secret || '-' }}</span>
              </div>
            </div>

            <div class="platform-footer">
              <el-button text type="primary" size="small" @click="openForm(item)">
                <el-icon><Edit /></el-icon> 编辑
              </el-button>
              <el-button text type="primary" size="small" @click="viewDetail(item.platform)">
                <el-icon><View /></el-icon> 通知绑定
              </el-button>
              <el-button text type="danger" size="small" @click="handleDelete(item)">
                <el-icon><Delete /></el-icon> 删除
              </el-button>
            </div>
          </div>
        </el-col>

        <el-col :span="24" v-if="!loading && !platforms.length">
          <el-empty description="暂无平台配置" />
        </el-col>
      </el-row>
    </div>

    <!-- 编辑弹窗 -->
    <PlatformForm
      v-if="formVisible"
      :visible="formVisible"
      :platform="currentPlatform"
      @close="formVisible = false"
      @saved="onSaved"
    />

    <!-- 通知绑定弹窗 -->
    <BindingConfig
      v-if="bindingVisible"
      :visible="bindingVisible"
      :platform="currentPlatformId"
      @close="bindingVisible = false"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getPlatforms, deletePlatform, updatePlatform } from '@/api/platforms'
import { platformColors, platformNames } from '@/utils/format'
import PlatformForm from './PlatformForm.vue'
import BindingConfig from '../notification/BindingConfig.vue'

const loading = ref(false)
const platforms = ref([])
const formVisible = ref(false)
const bindingVisible = ref(false)
const currentPlatform = ref(null)
const currentPlatformId = ref('')

async function loadData() {
  loading.value = true
  try {
    const res = await getPlatforms()
    platforms.value = Array.isArray(res) ? res : []
  } finally {
    loading.value = false
  }
}

function openForm(platform = null) {
  currentPlatform.value = platform
  formVisible.value = true
}

function viewDetail(platform) {
  currentPlatformId.value = platform
  bindingVisible.value = true
}

async function toggleEnabled(item, val) {
  try {
    await updatePlatform(item.platform, { enabled: val })
    item.enabled = val
    ElMessage.success(val ? '已启用' : '已禁用')
  } catch { /* 已处理 */ }
}

async function handleDelete(item) {
  await ElMessageBox.confirm(
    `确定要删除 ${platformNames[item.platform] || item.platform} 平台配置吗？`,
    '删除确认',
    { type: 'warning' }
  )
  try {
    await deletePlatform(item.platform)
    ElMessage.success('删除成功')
    loadData()
  } catch { /* 已处理 */ }
}

function onSaved() {
  formVisible.value = false
  loadData()
}

onMounted(loadData)
</script>

<style lang="scss" scoped>
.table-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.platform-card {
  background: $card-bg;
  border: 1px solid #ebeef5;
  border-radius: $border-radius;
  margin-bottom: 16px;
  transition: box-shadow 0.2s;
  overflow: hidden;

  &:hover {
    box-shadow: $card-shadow;
  }
}

.platform-header {
  padding: 16px 20px 12px;
  border-bottom: 1px solid #f0f0f0;
}

.platform-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.platform-desc {
  font-size: 13px;
  color: #909399;
  margin-top: 8px;
}

.platform-body {
  padding: 12px 20px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  font-size: 13px;
}

.info-label {
  color: #909399;
}

.info-value {
  color: #606266;
  font-family: monospace;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.platform-footer {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  padding: 8px 12px;
  border-top: 1px solid #f0f0f0;
  background: #fafafa;
}
</style>
