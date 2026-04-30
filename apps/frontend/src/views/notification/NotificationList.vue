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
          <div class="notify-card">
            <div class="notify-header">
              <div class="notify-info">
                <el-icon :size="24" :color="channelIcon[item.channel]?.color || '#409EFF'">
                  <component :is="channelIcon[item.channel]?.icon || 'Bell'" />
                </el-icon>
                <span class="channel-name">{{ channelNames[item.channel] || item.channel }}</span>
                <el-switch
                  :model-value="item.enabled"
                  @change="(val) => toggleEnabled(item, val)"
                  style="margin-left: auto"
                />
              </div>
              <p v-if="item.description" class="notify-desc">{{ item.description }}</p>
            </div>

            <div class="notify-body">
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
            </div>

            <div class="notify-footer">
              <el-button text type="primary" size="small" @click="openForm(item)">
                <el-icon><Edit /></el-icon> 编辑
              </el-button>
              <el-button text type="primary" size="small" @click="viewBindings(item.channel)">
                <el-icon><Connection /></el-icon> 平台绑定
              </el-button>
              <el-button text type="danger" size="small" @click="handleDelete(item)">
                <el-icon><Delete /></el-icon> 删除
              </el-button>
            </div>
          </div>
        </el-col>

        <el-col :span="24" v-if="!loading && !notifications.length">
          <el-empty description="暂无通知配置" />
        </el-col>
      </el-row>
    </div>

    <!-- 编辑弹窗 -->
    <NotificationForm
      v-if="formVisible"
      :visible="formVisible"
      :notification="currentNotification"
      @close="formVisible = false"
      @saved="onSaved"
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
import NotificationForm from './NotificationForm.vue'
import BindingConfig from './BindingConfig.vue'

const channelNames = { dingtalk: '钉钉', feishu: '飞书', wecom: '企业微信', slack: 'Slack' }
const channelIcon = {
  dingtalk: { icon: 'ChatDotRound', color: '#0089FF' },
  feishu: { icon: 'ChatLineRound', color: '#3370FF' },
  wecom: { icon: 'ChatDotRound', color: '#07C160' },
  slack: { icon: 'ChatLineRound', color: '#4A154B' }
}

const loading = ref(false)
const notifications = ref([])
const formVisible = ref(false)
const bindingVisible = ref(false)
const currentNotification = ref(null)
const currentChannelId = ref('')

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
  currentNotification.value = notification
  formVisible.value = true
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

.notify-card {
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

.notify-header {
  padding: 16px 20px 12px;
  border-bottom: 1px solid #f0f0f0;
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

.notify-body {
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
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.notify-footer {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  padding: 8px 12px;
  border-top: 1px solid #f0f0f0;
  background: #fafafa;
}
</style>
