<template>
  <div class="page-container">
    <div class="table-container">
      <div class="table-toolbar">
        <span class="table-title">通知配置</span>
        <el-button type="primary" @click="openForm()">
          <el-icon><Plus /></el-icon> 新增通知渠道
        </el-button>
      </div>

      <!-- 通知渠道卡片 -->
      <el-row :gutter="16" v-loading="loading">
        <el-col :xs="24" :sm="12" :lg="8" v-for="item in notifications" :key="item.channel">
          <ConfigCard>
            <template #header>
              <div class="notify-info">
                <el-icon :size="24" :color="channelIcons[item.channel]?.color || '#409EFF'">
                  <component :is="channelIcons[item.channel]?.icon || 'Bell'" />
                </el-icon>
                <span class="channel-name">{{ channelNames[item.channel] || item.channel }}</span>
                <el-switch
                  :model-value="item.enabled"
                  @change="(val) => toggleEnabled(item, val)"
                  style="margin-left: auto"
                />
              </div>
              <p v-if="item.description" class="notify-desc">{{ item.description }}</p>
            </template>

            <div class="info-row">
              <span class="info-label">Webhook URL</span>
              <span class="info-value">{{ item.webhook_url || '-' }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Secret</span>
              <span class="info-value">{{ item.secret || '-' }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">@手机号</span>
              <span class="info-value">{{ item.at_mobiles || '-' }}</span>
            </div>

            <template #footer>
              <el-button text type="primary" size="small" @click="openForm(item)">
                <el-icon><Edit /></el-icon> 编辑
              </el-button>
              <el-button text type="primary" size="small" @click="viewBindings(item.channel)">
                <el-icon><Connection /></el-icon> 平台绑定
              </el-button>
              <el-button text type="danger" size="small" @click="handleDelete(item)">
                <el-icon><Delete /></el-icon> 删除
              </el-button>
            </template>
          </ConfigCard>
        </el-col>

        <el-col :span="24" v-if="!loading && !notifications.length">
          <el-empty description="暂无通知配置" />
        </el-col>
      </el-row>
    </div>

    <!-- 编辑弹窗 -->
    <NotificationForm
      v-if="formDialog.visible.value"
      :visible="formDialog.visible.value"
      :notification="formDialog.currentItem.value"
      @close="formDialog.closeForm()"
      @saved="formDialog.onSaved(loadData)"
    />

    <!-- 平台绑定弹窗 -->
    <BindingConfig
      v-if="bindingVisible"
      :visible="bindingVisible"
      :channel="currentChannelId"
      @close="bindingVisible = false"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getNotifications, deleteNotification, updateNotification } from '@/api/notification'
import { channelNames, channelIcons } from '@/utils/format'
import ConfigCard from '@/components/common/ConfigCard.vue'
import { useFormDialog } from '@/composables/useFormDialog'
import NotificationForm from './NotificationForm.vue'
import BindingConfig from './BindingConfig.vue'

const loading = ref(false)
const notifications = ref([])
const bindingVisible = ref(false)
const currentChannelId = ref('')
const formDialog = useFormDialog()

async function loadData() {
  loading.value = true
  try {
    const res = await getNotifications()
    notifications.value = Array.isArray(res) ? res : []
  } finally {
    loading.value = false
  }
}

function openForm(notification = null) {
  formDialog.openForm(notification)
}

function viewBindings(channel) {
  currentChannelId.value = channel
  bindingVisible.value = true
}

async function toggleEnabled(item, val) {
  try {
    await updateNotification(item.channel, { enabled: val })
    item.enabled = val
    ElMessage.success(val ? '已启用' : '已禁用')
  } catch { /* 已处理 */ }
}

async function handleDelete(item) {
  await ElMessageBox.confirm(
    `确定要删除 ${channelNames[item.channel] || item.channel} 通知配置吗？`,
    '删除确认',
    { type: 'warning' }
  )
  try {
    await deleteNotification(item.channel)
    ElMessage.success('删除成功')
    loadData()
  } catch { /* 已处理 */ }
}

onMounted(loadData)
</script>

<style lang="scss" scoped>
.table-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.notify-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.channel-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.notify-desc {
  font-size: 13px;
  color: #909399;
  margin-top: 8px;
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
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
