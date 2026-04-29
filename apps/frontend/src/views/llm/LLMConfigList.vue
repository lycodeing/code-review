<template>
  <div class="page-container">
    <div class="table-container">
      <div class="table-toolbar">
        <span class="table-title">LLM 配置</span>
        <el-button type="primary" @click="openForm()">
          <el-icon><Plus /></el-icon> 新增配置
        </el-button>
      </div>

      <!-- 配置卡片展示 -->
      <el-row :gutter="16" v-loading="loading">
        <el-col :xs="24" :sm="12" :lg="8" v-for="item in configs" :key="item.id">
          <div class="config-card">
            <div class="config-header">
              <div class="config-info">
                <el-tag
                  :color="providerColors[item.provider] || ''"
                  effect="dark"
                  size="large"
                  style="border: none"
                >
                  {{ providerNames[item.provider] || item.provider }}
                </el-tag>
                <el-tag v-if="item.name === 'default'" type="warning" size="small" style="margin-left: 8px">
                  全局默认
                </el-tag>
                <el-switch
                  :model-value="item.enabled"
                  @change="(val) => toggleEnabled(item, val)"
                  style="margin-left: auto"
                />
              </div>
              <h3 class="config-name">{{ item.name }}</h3>
              <p v-if="item.description" class="config-desc">{{ item.description }}</p>
            </div>

            <div class="config-body">
              <div class="info-row">
                <span class="info-label">模型</span>
                <span class="info-value">{{ item.model_name }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">响应格式</span>
                <span class="info-value">
                  <el-tag :type="getResponseFormatTagType(item.response_format)" size="small">
                    {{ getResponseFormatLabel(item.response_format) }}
                  </el-tag>
                </span>
              </div>
              <div class="info-row">
                <span class="info-label">API Base</span>
                <span class="info-value">{{ item.api_base || '-' }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">API Key</span>
                <span class="info-value">{{ item.api_key || '-' }}</span>
              </div>
              <div v-if="item.extra_params" class="info-row">
                <span class="info-label">额外参数</span>
                <span class="info-value">{{ formatExtraParams(item.extra_params) }}</span>
              </div>
            </div>

            <div class="config-footer">
              <el-button text type="primary" size="small" @click="handleQuickTest(item)" :loading="testingConfigId === item.id">
                <el-icon><Connection /></el-icon> 测试
              </el-button>
              <el-button text type="primary" size="small" @click="openForm(item)">
                <el-icon><Edit /></el-icon> 编辑
              </el-button>
              <el-button text type="danger" size="small" @click="handleDelete(item)">
                <el-icon><Delete /></el-icon> 删除
              </el-button>
            </div>
          </div>
        </el-col>

        <el-col :span="24" v-if="!loading && !configs.length">
          <el-empty description="暂无 LLM 配置" />
        </el-col>
      </el-row>
    </div>

    <!-- 编辑弹窗 -->
    <LLMConfigForm
      v-if="formVisible"
      :visible="formVisible"
      :config="currentConfig"
      @close="formVisible = false"
      @saved="onSaved"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Connection } from '@element-plus/icons-vue'
import {
  getLLMConfigs,
  deleteLLMConfig,
  toggleLLMConfig,
  testLLMConfigById
} from '@/api/llmConfigs'
import LLMConfigForm from './LLMConfigForm.vue'

const loading = ref(false)
const configs = ref([])
const formVisible = ref(false)
const currentConfig = ref(null)
const testingConfigId = ref(null)

const providerColors = {
  openai: '#10a37f',
  anthropic: '#d4a574',
  deepseek: '#6366f1',
  ollama: '#000000',
  azure: '#0078d4',
  bedrock: '#232f3e',
  dashscope: '#ff6a00'
}

const providerNames = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  deepseek: 'DeepSeek',
  ollama: 'Ollama',
  azure: 'Azure',
  bedrock: 'AWS Bedrock',
  dashscope: 'Dashscope (阿里云)',
  zhipu: '智谱 AI (Zhipu)'
}

const responseFormatLabels = {
  auto: '自动检测',
  json: 'JSON',
  anthropic_thinking: 'Anthropic Thinking',
  xml: 'XML',
  plain_text: '纯文本'
}

const responseFormatTypes = {
  auto: 'info',
  json: 'success',
  anthropic_thinking: 'warning',
  xml: '',
  plain_text: 'info'
}

function getResponseFormatLabel(format) {
  return responseFormatLabels[format] || format
}

function getResponseFormatTagType(format) {
  return responseFormatTypes[format] || ''
}

async function loadData() {
  loading.value = true
  try {
    const res = await getLLMConfigs()
    configs.value = Array.isArray(res) ? res : []
  } finally {
    loading.value = false
  }
}

function formatExtraParams(params) {
  const keys = Object.keys(params).slice(0, 2)
  return keys.map(k => `${k}: ${params[k]}`).join(', ') + (Object.keys(params).length > 2 ? '...' : '')
}

function openForm(config = null) {
  currentConfig.value = config
  formVisible.value = true
}

async function toggleEnabled(item, val) {
  try {
    await toggleLLMConfig(item.id, val)
    item.enabled = val
    ElMessage.success(val ? '已启用' : '已禁用')
  } catch { /* 已处理 */ }
}

async function handleQuickTest(item) {
  testingConfigId.value = item.id
  try {
    const result = await testLLMConfigById(item.id)
    if (result.success) {
      ElMessage.success(`连接成功 (${result.response_time_ms}ms)`)
    } else {
      ElMessage.error(`连接失败: ${result.message}`)
    }
  } catch (e) {
    ElMessage.error(`连接失败: ${e.message || '未知错误'}`)
  } finally {
    testingConfigId.value = null
  }
}

async function handleDelete(item) {
  await ElMessageBox.confirm(
    `确定要删除 LLM 配置 "${item.name}" 吗？`,
    '删除确认',
    { type: 'warning' }
  )
  try {
    await deleteLLMConfig(item.id)
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

.config-card {
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

.config-header {
  padding: 16px 20px 12px;
  border-bottom: 1px solid #f0f0f0;
}

.config-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.config-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin: 8px 0 4px;
}

.config-desc {
  font-size: 13px;
  color: #909399;
  margin: 4px 0 0;
}

.config-body {
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
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.config-footer {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  padding: 8px 12px;
  border-top: 1px solid #f0f0f0;
  background: #fafafa;
}
</style>
