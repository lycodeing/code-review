<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑模板' : '新增模板'"
    width="680px"
    destroy-on-close
    @close="emit('close')"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
      <el-form-item label="模板名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入模板名称" />
      </el-form-item>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="类别" prop="category">
            <el-select v-model="form.category" placeholder="选择类别" style="width: 100%">
              <el-option label="默认" value="default" />
              <el-option label="Python" value="python" />
              <el-option label="Java" value="java" />
              <el-option label="Go" value="go" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="语言" prop="locale">
            <el-select v-model="form.locale" placeholder="选择语言" style="width: 100%">
              <el-option label="中文" value="zh" />
              <el-option label="English" value="en" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="启用状态">
        <el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" />
      </el-form-item>

      <el-form-item label="模板内容" prop="content">
        <el-input
          v-model="form.content"
          type="textarea"
          :rows="14"
          placeholder="支持 {{diff}} 和 {{files_context}} 占位符"
        />
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
import { createTemplate, updateTemplate } from '@/api/template'

const props = defineProps({
  visible: Boolean,
  template: { type: Object, default: null }
})
const emit = defineEmits(['close', 'saved'])

const formRef = ref(null)
const submitting = ref(false)
const isEdit = computed(() => !!props.template)

const form = reactive({
  name: '',
  category: 'default',
  locale: 'zh',
  enabled: 1,
  content: ''
})

const rules = {
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
  content: [{ required: true, message: '请输入模板内容', trigger: 'blur' }]
}

watch(
  () => props.template,
  (val) => {
    if (val) {
      Object.assign(form, {
        name: val.name || '',
        category: val.category || 'default',
        locale: val.locale || 'zh',
        enabled: val.enabled ?? 1,
        content: val.content || ''
      })
    } else {
      Object.assign(form, { name: '', category: 'default', locale: 'zh', enabled: 1, content: '' })
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
      await updateTemplate(props.template.id, form)
      ElMessage.success('更新成功')
    } else {
      await createTemplate(form)
      ElMessage.success('创建成功')
    }
    emit('saved')
  } finally {
    submitting.value = false
  }
}
</script>
