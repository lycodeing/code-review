<template>
  <el-dialog
    :model-value="visible"
    title="平台 - 通知绑定"
    width="560px"
    destroy-on-close
    @close="emit('close')"
  >
    <div v-loading="loading">
      <p class="bind-hint" v-if="channel">
        配置「{{ channelNames[channel] || channel }}」通知渠道绑定的平台
      </p>
      <p class="bind-hint" v-else-if="platform">
        配置「{{ platformNames[platform] || platform }}」平台绑定的通知渠道
      </p>

      <el-table :data="bindings" stripe>
        <el-table-column :label="platform ? '通知渠道' : '平台'" min-width="140">
          <template #default="{ row }">
            <span v-if="platform">{{ channelNames[row.channel] || row.channel }}</span>
            <span v-else>{{ platformNames[row.platform] || row.platform }}</span>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="100" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" @change="handleBindingChange(row)" />
          </template>
        </el-table-column>
      </el-table>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getNotification, updateBinding } from '@/api/notification'
import { getPlatform } from '@/api/platforms'
import { platformNames } from '@/utils/format'

const channelNames = { dingtalk: '钉钉', feishu: '飞书', wecom: '企业微信', slack: 'Slack' }

const props = defineProps({
  visible: Boolean,
  platform: { type: String, default: '' },
  channel: { type: String, default: '' }
})
const emit = defineEmits(['close'])

const loading = ref(false)
const bindings = ref([])

async function loadBindings() {
  loading.value = true
  try {
    if (props.channel) {
      const res = await getNotification(props.channel)
      bindings.value = (res.platforms || []).map((b) => ({
        channel: props.channel,
        platform: b.platform,
        enabled: b.enabled
      }))
    } else if (props.platform) {
      const res = await getPlatform(props.platform)
      bindings.value = (res.notifications || []).map((b) => ({
        platform: props.platform,
        channel: b.channel,
        enabled: b.enabled
      }))
    }
  } finally {
    loading.value = false
  }
}

async function handleBindingChange(row) {
  try {
    await updateBinding(row.channel, {
      platform: row.platform,
      enabled: row.enabled
    })
    ElMessage.success(row.enabled ? '已启用绑定' : '已禁用绑定')
  } catch {
    row.enabled = !row.enabled
  }
}

onMounted(loadBindings)
</script>

<style lang="scss" scoped>
.bind-hint {
  font-size: 14px;
  color: #606266;
  margin-bottom: 16px;
}
</style>
