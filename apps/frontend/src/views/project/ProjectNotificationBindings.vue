<template>
  <el-dialog
    :model-value="visible"
    :title="`通知模板绑定 — ${projectName}`"
    width="640px"
    destroy-on-close
    @close="emit('close')"
  >
    <div v-loading="loading">
      <div class="hint">为该项目的每个通知渠道指定使用的通知模板，不选则使用渠道默认模板。</div>

      <el-empty v-if="!loading && !notificationConfigs.length" description="该项目暂无关联的通知渠道配置" :image-size="60" />

      <el-form v-else label-width="90px" size="default" style="margin-top: 16px">
        <el-form-item
          v-for="nc in notificationConfigs"
          :key="nc.id"
          :label="channelLabel(nc.channel)"
        >
          <el-select
            v-model="bindingMap[nc.id]"
            placeholder="使用渠道默认模板"
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="tpl in templatesByChannel[nc.channel] || []"
              :key="tpl.id"
              :label="tpl.name + (tpl.is_default ? '（默认）' : '')"
              :value="tpl.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <el-button @click="emit('close')">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { getNotifications } from '@/api/notification'
import { getNotificationTemplates, getProjectNotificationBindings, updateProjectNotificationBindings } from '@/api/notificationTemplates'

const props = defineProps({
  visible: Boolean,
  projectId: { type: String, required: true },
  projectName: { type: String, default: '' },
})
const emit = defineEmits(['close'])

const loading = ref(false)
const saving = ref(false)
const notificationConfigs = ref([])
const allTemplates = ref([])
// key: notification_config.id → template_id | null
const bindingMap = reactive({})

const channelNames = { dingtalk: '🔔 钉钉', feishu: '🔵 飞书' }
function channelLabel(ch) {
  return channelNames[ch] || ch
}

const templatesByChannel = computed(() => {
  const map = {}
  for (const tpl of allTemplates.value) {
    if (!map[tpl.channel]) map[tpl.channel] = []
    map[tpl.channel].push(tpl)
  }
  return map
})

async function loadData() {
  if (!props.projectId) return
  loading.value = true
  try {
    const [confsRes, tplsRes, bindingsRes] = await Promise.all([
      getNotifications(),
      getNotificationTemplates(),
      getProjectNotificationBindings(props.projectId),
    ])

    notificationConfigs.value = Array.isArray(confsRes) ? confsRes : (confsRes?.items || [])
    allTemplates.value = Array.isArray(tplsRes) ? tplsRes : (tplsRes?.items || [])

    const bindings = Array.isArray(bindingsRes) ? bindingsRes : []

    // 初始化 bindingMap：notification_id → template_id
    for (const nc of notificationConfigs.value) {
      const found = bindings.find(b => b.notification_id === nc.id)
      bindingMap[nc.id] = found?.template_id || null
    }
  } catch (e) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  saving.value = true
  try {
    const payload = notificationConfigs.value.map(nc => ({
      notification_id: nc.id,
      template_id: bindingMap[nc.id] || null,
      enabled: true,
    }))
    await updateProjectNotificationBindings(props.projectId, payload)
    ElMessage.success('保存成功')
    emit('close')
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

watch(() => props.visible, val => {
  if (val) loadData()
}, { immediate: true })
</script>

<style scoped>
.hint {
  font-size: 13px;
  color: #909399;
  background: #f5f7fa;
  padding: 10px 14px;
  border-radius: 6px;
}
</style>
