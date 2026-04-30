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
          <el-option label="企业微信" value="wecom" />
          <el-option label="Slack" value="slack" />
          <el-option label="邮件" value="email" />
        </el-select>
      </el-form-item>

      <!-- IM 渠道通用配置 -->
      <template v-if="form.channel !== 'email'">
        <el-form-item label="Webhook URL" prop="webhook_url">
          <el-input v-model="form.webhook_url" placeholder="通知 Webhook 地址" />
        </el-form-item>

        <el-form-item label="Secret">
          <el-input v-model="form.secret" placeholder="签名密钥（可选）" show-password />
        </el-form-item>

        <el-form-item label="@手机号">
          <el-input v-model="form.at_mobiles" placeholder="多人用逗号分隔" />
        </el-form-item>
      </template>

      <!-- Email 渠道专属配置 -->
      <template v-if="form.channel === 'email'">
        <el-form-item label="SMTP 主机" prop="extra_config.smtp_host">
          <el-input v-model="form.extra_config.smtp_host" placeholder="如 smtp.example.com" />
        </el-form-item>

        <el-form-item label="SMTP 端口">
          <el-input-number v-model="form.extra_config.smtp_port" :min="1" :max="65535" />
        </el-form-item>

        <el-form-item label="SMTP 用户">
          <el-input v-model="form.extra_config.smtp_user" placeholder="SMTP 登录用户名" />
        </el-form-item>

        <el-form-item label="SMTP 密码">
          <el-input v-model="form.extra_config.smtp_password" placeholder="SMTP 登录密码" show-password />
        </el-form-item>

        <el-form-item label="发件人地址">
          <el-input v-model="form.extra_config.from_addr" placeholder="noreply@example.com" />
        </el-form-item>

        <el-form-item label="收件人地址">
          <el-input
            v-model="extraAddrsText"
            placeholder="多个收件人用逗号分隔"
            @blur="parseAddrs"
          />
        </el-form-item>
      </template>

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

const extraAddrsText = ref('')

const form = reactive({
  channel: '',
  webhook_url: '',
  secret: '',
  at_mobiles: '',
  description: '',
  enabled: true,
  extra_config: {
    smtp_host: '',
    smtp_port: 587,
    smtp_user: '',
    smtp_password: '',
    from_addr: '',
    to_addrs: [],
  }
})

const rules = computed(() => {
  const base = {
    channel: [{ required: true, message: '请选择通知渠道', trigger: 'change' }],
  }
  if (form.channel !== 'email') {
    base.webhook_url = [{ required: true, message: '请输入 Webhook URL', trigger: 'blur' }]
  } else {
    base['extra_config.smtp_host'] = [{ required: true, message: '请输入 SMTP 主机', trigger: 'blur' }]
  }
  return base
})

function parseAddrs() {
  form.extra_config.to_addrs = extraAddrsText.value
    .split(',')
    .map(s => s.trim())
    .filter(Boolean)
}

watch(
  () => props.notification,
  (val) => {
    if (val) {
      const extra = val.extra_config || {}
      Object.assign(form, {
        channel: val.channel || '',
        webhook_url: val.webhook_url || '',
        secret: '',
        at_mobiles: val.at_mobiles || '',
        description: val.description || '',
        enabled: val.enabled ?? true,
        extra_config: {
          smtp_host: extra.smtp_host || '',
          smtp_port: extra.smtp_port || 587,
          smtp_user: extra.smtp_user || '',
          smtp_password: extra.smtp_password || '',
          from_addr: extra.from_addr || '',
          to_addrs: extra.to_addrs || [],
        }
      })
      extraAddrsText.value = (extra.to_addrs || []).join(', ')
    } else {
      Object.assign(form, {
        channel: '', webhook_url: '', secret: '',
        at_mobiles: '', description: '', enabled: true,
        extra_config: {
          smtp_host: '', smtp_port: 587, smtp_user: '',
          smtp_password: '', from_addr: '', to_addrs: [],
        }
      })
      extraAddrsText.value = ''
    }
  },
  { immediate: true }
)

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  parseAddrs()

  submitting.value = true
  try {
    const payload = { ...form }
    // 非邮箱渠道不发送 extra_config
    if (payload.channel !== 'email') {
      delete payload.extra_config
    }
    if (isEdit.value) {
      await updateNotification(props.notification.channel, payload)
      ElMessage.success('更新成功')
    } else {
      await createNotification(payload)
      ElMessage.success('创建成功')
    }
    emit('saved')
  } finally {
    submitting.value = false
  }
}
</script>
