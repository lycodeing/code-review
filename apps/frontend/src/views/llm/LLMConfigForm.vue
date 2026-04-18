<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑 LLM 配置' : '新增 LLM 配置'"
    width="560px"
    destroy-on-close
    @close="emit('close')"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
      <el-form-item label="配置名称" prop="name">
        <el-input
          v-model="form.name"
          placeholder="如: deepseek-chat, claude-3-5"
          :disabled="isEdit && form.name === 'default'"
        />
      </el-form-item>

      <el-form-item label="提供商" prop="provider">
        <el-select
          v-model="form.provider"
          placeholder="选择 LLM 提供商"
          style="width: 100%"
        >
          <el-option label="OpenAI" value="openai" />
          <el-option label="Anthropic" value="anthropic" />
          <el-option label="DeepSeek" value="deepseek" />
          <el-option label="Ollama" value="ollama" />
          <el-option label="Azure OpenAI" value="azure" />
          <el-option label="AWS Bedrock" value="bedrock" />
          <el-option label="Dashscope (阿里云)" value="dashscope" />
          <el-option label="智谱 AI (Zhipu)" value="zhipu" />
        </el-select>
      </el-form-item>

      <el-form-item label="模型名称" prop="model_name">
        <el-input
          v-model="form.model_name"
          placeholder="如: gpt-4o, claude-3-5-sonnet-20241022, deepseek-chat"
        />
        <div class="form-tip">
          <a href="https://docs.litellm.ai/" target="_blank">查看支持的模型列表</a>
        </div>
      </el-form-item>

      <el-form-item label="API Key" prop="api_key">
        <el-input
          v-model="form.api_key"
          type="password"
          placeholder="API 密钥"
          show-password
        />
      </el-form-item>

      <el-form-item label="API Base URL">
        <el-input
          v-model="form.api_base"
          placeholder="如: https://api.openai.com/v1（可选）"
        />
      </el-form-item>

      <el-form-item label="响应格式" prop="response_format">
        <el-select
          v-model="form.response_format"
          placeholder="选择响应格式"
          style="width: 100%"
          @change="onResponseFormatChange"
        >
          <el-option label="自动检测（推荐）" value="auto">
            <div style="display: flex; align-items: center; justify-content: space-between;">
              <span>自动检测</span>
              <el-tag size="small" type="info">推荐</el-tag>
            </div>
          </el-option>
          <el-option label="JSON 格式" value="json">
            <div style="display: flex; align-items: center; justify-content: space-between;">
              <span>JSON</span>
              <el-tag size="small" type="success">OpenAI/Zhipu/DeepSeek</el-tag>
            </div>
          </el-option>
          <el-option label="Anthropic Thinking" value="anthropic_thinking">
            <div style="display: flex; align-items: center; justify-content: space-between;">
              <span>Anthropic Thinking</span>
              <el-tag size="small" type="warning">Claude</el-tag>
            </div>
          </el-option>
          <el-option label="XML 格式" value="xml">
            <span>XML</span>
          </el-option>
          <el-option label="纯文本" value="plain_text">
            <span>纯文本</span>
          </el-option>
        </el-select>
        <div class="form-tip">
          <div v-if="responseFormatInfo.description">{{ responseFormatInfo.description }}</div>
          <div v-if="responseFormatInfo.providers" style="margin-top: 4px;">
            <strong>适用提供商：</strong>{{ responseFormatInfo.providers }}
          </div>
        </div>
      </el-form-item>

      <el-form-item label="额外参数">
        <el-input
          v-model="extraParamsJson"
          type="textarea"
          :rows="3"
          placeholder='JSON 格式，如: {"temperature": 0.3, "max_tokens": 4096}'
          @blur="validateExtraParams"
        />
        <div v-if="extraParamsError" class="form-tip error">{{ extraParamsError }}</div>
      </el-form-item>

      <el-form-item label="描述">
        <el-input
          v-model="form.description"
          placeholder="配置描述（可选）"
        />
      </el-form-item>

      <el-form-item label="启用">
        <el-switch v-model="form.enabled" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="emit('close')">取消</el-button>
      <el-button @click="handleTestConnection" :loading="testing" :type="testResult?.success ? 'success' : 'default'" plain>
        <el-icon><Connection /></el-icon> 测试连接
      </el-button>
      <span v-if="testResult" :style="{ marginLeft: '12px', color: testResult.success ? 'green' : 'red', fontSize: '12px' }">
        {{ testResult.message }}
        <span v-if="testResult.response_time_ms !== null"> ({{ testResult.response_time_ms }}ms)</span>
      </span>
      <el-button type="primary" :loading="submitting" @click="handleSubmit" style="margin-left: auto">
        {{ isEdit ? '保存' : '创建' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Connection } from '@element-plus/icons-vue'
import { createLLMConfig, updateLLMConfig, testLLMConnection } from '@/api/llmConfigs'

const props = defineProps({
  visible: Boolean,
  config: { type: Object, default: null }
})
const emit = defineEmits(['close', 'saved'])

const formRef = ref(null)
const submitting = ref(false)
const testing = ref(false)
const testResult = ref(null)
const extraParamsJson = ref('')
const extraParamsError = ref('')

const isEdit = computed(() => !!props.config)

const form = reactive({
  name: '',
  provider: 'openai',
  model_name: '',
  api_key: '',
  api_base: '',
  extra_params: null,
  response_format: 'auto',
  enabled: true,
  description: ''
})

const rules = {
  name: [
    { required: true, message: '请输入配置名称', trigger: 'blur' },
    { min: 1, max: 255, message: '长度在 1 到 255 个字符', trigger: 'blur' }
  ],
  provider: [{ required: true, message: '请选择提供商', trigger: 'change' }],
  model_name: [
    { required: true, message: '请输入模型名称', trigger: 'blur' },
    { min: 1, max: 128, message: '长度在 1 到 128 个字符', trigger: 'blur' }
  ],
  response_format: [{ required: true, message: '请选择响应格式', trigger: 'change' }]
}

// 响应格式信息映射
const responseFormatInfoMap = {
  auto: {
    description: '自动检测响应格式（推荐）。系统会自动识别 LLM 返回的格式并使用相应的解析器。',
    providers: '所有提供商'
  },
  json: {
    description: '标准 JSON 格式。适用于大多数 OpenAI 兼容的 API，返回结构化的 JSON 数据。',
    providers: 'OpenAI, Zhipu AI, DeepSeek, 通义千问'
  },
  anthropic_thinking: {
    description: 'Anthropic Thinking 模式。支持 Claude 的扩展思考功能，返回推理过程和结果。',
    providers: 'Anthropic Claude'
  },
  xml: {
    description: 'XML 格式。某些特定提供商可能使用 XML 格式返回响应。',
    providers: '特定提供商'
  },
  plain_text: {
    description: '纯文本格式。作为降级方案，使用正则表达式尝试提取结构化信息。',
    providers: '所有提供商（降级）'
  }
}

const responseFormatInfo = ref(responseFormatInfoMap.auto)

function onResponseFormatChange(format) {
  responseFormatInfo.value = responseFormatInfoMap[format] || responseFormatInfoMap.auto

  // 根据提供商推荐格式
  recommendFormatForProvider()
}

function recommendFormatForProvider() {
  const provider = form.provider
  let recommendedFormat = 'auto'

  // Anthropic 推荐 thinking 模式
  if (provider === 'anthropic' && form.response_format === 'auto') {
    form.response_format = 'anthropic_thinking'
  }
  // 其他提供商推荐 json 格式（保持 auto 即可）
}

watch(
  () => props.config,
  (val) => {
    if (val) {
      Object.assign(form, {
        name: val.name || '',
        provider: val.provider || 'openai',
        model_name: val.model_name || '',
        api_key: '',  // 编辑时不显示原密钥
        api_base: val.api_base || '',
        extra_params: val.extra_params || null,
        response_format: val.response_format || 'auto',
        enabled: val.enabled ?? true,
        description: val.description || ''
      })
      extraParamsJson.value = val.extra_params ? JSON.stringify(val.extra_params, null, 2) : ''

      // 更新响应格式信息
      onResponseFormatChange(form.response_format)
    } else {
      Object.assign(form, {
        name: '', provider: 'openai', model_name: '', api_key: '',
        api_base: '', extra_params: null, response_format: 'auto',
        enabled: true, description: ''
      })
      extraParamsJson.value = ''
      onResponseFormatChange('auto')
    }
    testResult.value = null
  },
  { immediate: true }
)

function validateExtraParams() {
  const jsonStr = extraParamsJson.value.trim()
  if (!jsonStr) {
    form.extra_params = null
    extraParamsError.value = ''
    return
  }
  try {
    form.extra_params = JSON.parse(jsonStr)
    extraParamsError.value = ''
  } catch (e) {
    extraParamsError.value = 'JSON 格式不正确'
  }
}

async function handleTestConnection() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  // 验证额外参数
  if (extraParamsJson.value.trim()) {
    try {
      form.extra_params = JSON.parse(extraParamsJson.value)
    } catch {
      ElMessage.error('额外参数 JSON 格式不正确')
      return
    }
  }

  testing.value = true
  testResult.value = null
  try {
    const res = await testLLMConnection({
      provider: form.provider,
      model_name: form.model_name,
      api_key: form.api_key,
      api_base: form.api_base,
      extra_params: form.extra_params,
      response_format: form.response_format
    })
    testResult.value = res
    if (res.success) {
      ElMessage.success('连接测试成功')
    } else {
      ElMessage.error('连接测试失败')
    }
  } catch (e) {
    testResult.value = {
      success: false,
      message: '连接测试失败: ' + (e.message || '未知错误')
    }
  } finally {
    testing.value = false
  }
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  // 验证额外参数
  validateExtraParams()
  if (extraParamsError.value) {
    ElMessage.error('请修正额外参数格式')
    return
  }

  submitting.value = true
  try {
    if (isEdit.value) {
      await updateLLMConfig(props.config.id, form)
      ElMessage.success('更新成功')
    } else {
      await createLLMConfig(form)
      ElMessage.success('创建成功')
    }
    emit('saved')
  } finally {
    submitting.value = false
  }
}
</script>

<style lang="scss" scoped>
.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;

  &.error {
    color: #f56c6c;
  }

  a {
    color: #409eff;
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }
}
</style>
