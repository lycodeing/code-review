<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑通知配置' : '新增通知渠道'"
    width="520px"
    destroy-on-close
    @close="emit('close')"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
      <el-form-item label="通知渠道" prop="channel">
        <el-select
          v-model="form.channel"
          placeholder="选择通知渠道"
          :disabled="isEdit"
          style="width: 100%"
        >
          <el-option label="钉钉" value="dingtalk" />
          <el-option label="飞书" value="feishu" />
        </el-select>
      </el-form-item>

      <el-form-item label="Webhook URL" prop="webhook_url">
        <el-input v-model="form.webhook_url" placeholder="通知 Webhook 地址" />
      </el-form-item>

      <el-form-item label="Secret">
        <el-input v-model="form.secret" placeholder="签名密钥（可选）" show-password />
      </el-form-item>

      <el-form-item label="@手机号">
        <el-input v-model="form.at_mobiles" placeholder="多人用逗号分隔" />
      </el-form-item>

      <el-form-item label="描述">
        <el-input v-model="form.description" placeholder="通知配置描述（可选）" />
      </el-form-item>

      <el-form-item label="启用">
        <el-switch v-model="form.enabled" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="emit('close')">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        {{ isEdit ? '保存' : '创建' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createNotification, updateNotification } from '@/api/notification'

const props = defineProps({
  visible: Boolean,
  notification: { type: Object, default: null }
})
const emit = defineEmits(['close', 'saved'])

const formRef = ref(null)
const submitting = ref(false)
const isEdit = computed(() => !!props.notification)

const form = reactive({
  channel: '',
  webhook_url: '',
  secret: '',
  at_mobiles: '',
  description: '',
  enabled: true
})

const rules = {
  channel: [{ required: true, message: '请选择通知渠道', trigger: 'change' }],
  webhook_url: [{ required: true, message: '请输入 Webhook URL', trigger: 'blur' }]
}

watch(
  () => props.notification,
  (val) => {
    if (val) {
      Object.assign(form, {
        channel: val.channel || '',
        webhook_url: val.webhook_url || '',
        secret: '',
        at_mobiles: val.at_mobiles || '',
        description: val.description || '',
        enabled: val.enabled ?? true
      })
    } else {
      Object.assign(form, {
        channel: '', webhook_url: '', secret: '',
        at_mobiles: '', description: '', enabled: true
      })
    }
  },
  { immediate: true }
)

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (isEdit.value) {
      await updateNotification(props.notification.channel, form)
      ElMessage.success('更新成功')
    } else {
      await createNotification(form)
      ElMessage.success('创建成功')
    }
    emit('saved')
  } finally {
    submitting.value = false
  }
}
</script>
