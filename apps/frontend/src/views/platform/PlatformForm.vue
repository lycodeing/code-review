<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑平台配置' : '新增平台配置'"
    width="520px"
    destroy-on-close
    @close="emit('close')"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
      <el-form-item label="平台" prop="platform">
        <el-select
          v-model="form.platform"
          placeholder="选择平台"
          :disabled="isEdit"
          style="width: 100%"
        >
          <el-option label="GitHub" value="github" />
          <el-option label="GitLab" value="gitlab" />
          <el-option label="Gitee" value="gitee" />
        </el-select>
      </el-form-item>

      <el-form-item label="Access Token">
        <el-input v-model="form.access_token" placeholder="API 访问令牌" show-password />
      </el-form-item>

      <el-form-item label="Webhook Secret">
        <el-input v-model="form.webhook_secret" placeholder="Webhook 签名密钥" show-password />
      </el-form-item>

      <el-form-item label="API 地址">
        <el-input v-model="form.api_url" placeholder="如 https://api.github.com" />
      </el-form-item>

      <el-form-item label="描述">
        <el-input v-model="form.description" placeholder="平台配置描述（可选）" />
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
import { createPlatform, updatePlatform } from '@/api/platforms'

const props = defineProps({
  visible: Boolean,
  platform: { type: Object, default: null }
})
const emit = defineEmits(['close', 'saved'])

const formRef = ref(null)
const submitting = ref(false)
const isEdit = computed(() => !!props.platform)

const form = reactive({
  platform: '',
  access_token: '',
  webhook_secret: '',
  api_url: '',
  description: '',
  enabled: true
})

const rules = {
  platform: [{ required: true, message: '请选择平台', trigger: 'change' }]
}

watch(
  () => props.platform,
  (val) => {
    if (val) {
      Object.assign(form, {
        platform: val.platform || '',
        access_token: '',
        webhook_secret: '',
        api_url: val.api_url || '',
        description: val.description || '',
        enabled: val.enabled ?? true
      })
    } else {
      Object.assign(form, {
        platform: '', access_token: '', webhook_secret: '',
        api_url: '', description: '', enabled: true
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
      await updatePlatform(props.platform.platform, form)
      ElMessage.success('更新成功')
    } else {
      await createPlatform(form)
      ElMessage.success('创建成功')
    }
    emit('saved')
  } finally {
    submitting.value = false
  }
}
</script>
