<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑项目' : '新增项目'"
    width="560px"
    destroy-on-close
    @close="emit('close')"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
      <el-form-item label="项目名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入项目名称" />
      </el-form-item>

      <el-form-item label="代码平台" prop="platform">
        <el-select v-model="form.platform" placeholder="请选择平台" :disabled="isEdit" style="width: 100%">
          <el-option label="GitHub" value="github" />
          <el-option label="GitLab" value="gitlab" />
          <el-option label="Gitee" value="gitee" />
        </el-select>
      </el-form-item>

      <el-form-item label="平台项目 ID" prop="platform_project_id">
        <el-input v-model="form.platform_project_id" placeholder="平台上的项目标识" :disabled="isEdit" />
      </el-form-item>

      <el-form-item label="Webhook 密钥" prop="webhook_secret">
        <el-input v-model="form.webhook_secret" placeholder="Webhook 签名密钥（可选）" show-password />
      </el-form-item>

      <el-form-item label="启用状态">
        <el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" />
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
import { createProject, updateProject } from '@/api/projects'

const props = defineProps({
  visible: Boolean,
  project: { type: Object, default: null }
})
const emit = defineEmits(['close', 'saved'])

const formRef = ref(null)
const submitting = ref(false)
const isEdit = computed(() => !!props.project)

const form = reactive({
  name: '',
  platform: '',
  platform_project_id: '',
  webhook_secret: '',
  enabled: 1
})

const rules = {
  name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
  platform: [{ required: true, message: '请选择平台', trigger: 'change' }],
  platform_project_id: [{ required: true, message: '请输入平台项目 ID', trigger: 'blur' }]
}

// 编辑时填充表单
watch(
  () => props.project,
  (val) => {
    if (val) {
      Object.assign(form, {
        name: val.name || '',
        platform: val.platform || '',
        platform_project_id: val.platform_project_id || '',
        webhook_secret: '',
        enabled: val.enabled ?? 1
      })
    } else {
      Object.assign(form, { name: '', platform: '', platform_project_id: '', webhook_secret: '', enabled: 1 })
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
      await updateProject(props.project.id, form)
      ElMessage.success('更新成功')
    } else {
      await createProject(form)
      ElMessage.success('创建成功')
    }
    emit('saved')
  } finally {
    submitting.value = false
  }
}
</script>
