<template>
  <div class="page-container">
    <el-row :gutter="16" style="height: 100%">
      <!-- 左侧：模板列表 -->
      <el-col :span="7">
        <div class="table-container" style="height: 100%">
          <div class="table-toolbar">
            <span class="table-title">通知模板</span>
            <el-button type="primary" size="small" @click="openCreate">
              <el-icon><Plus /></el-icon> 新增
            </el-button>
          </div>

          <div class="channel-group" v-for="(group, channel) in groupedTemplates" :key="channel">
            <div class="channel-label">
              <el-icon :color="channelColor[channel]"><Bell /></el-icon>
              {{ channelNames[channel] || channel }}
            </div>
            <div
              v-for="tpl in group"
              :key="tpl.id"
              class="tpl-item"
              :class="{ active: currentTemplate?.id === tpl.id }"
              @click="selectTemplate(tpl)"
            >
              <span class="tpl-name">{{ tpl.name }}</span>
              <el-tag v-if="tpl.is_default" size="small" type="info">默认</el-tag>
              <el-tag v-else-if="!tpl.enabled" size="small" type="danger">禁用</el-tag>
            </div>
          </div>

          <el-empty v-if="!loading && !templates.length" description="暂无模板" :image-size="60" />
        </div>
      </el-col>

      <!-- 右侧：编辑 + 预览 -->
      <el-col :span="17">
        <div class="table-container" v-if="currentTemplate" v-loading="saving">
          <div class="table-toolbar">
            <span class="table-title">{{ isCreating ? '新增模板' : currentTemplate.name }}</span>
            <div>
              <el-button
                v-if="!isCreating && !currentTemplate.is_default"
                type="danger"
                size="small"
                plain
                @click="handleDelete"
              >
                <el-icon><Delete /></el-icon> 删除
              </el-button>
              <el-button type="primary" size="small" @click="handleSave">
                <el-icon><Check /></el-icon> 保存
              </el-button>
            </div>
          </div>

          <el-form :model="form" label-width="90px" size="default" style="padding: 0 8px">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="模板名称">
                  <el-input v-model="form.name" placeholder="请输入模板名称" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="渠道">
                  <el-select v-model="form.channel" :disabled="!isCreating" style="width: 100%">
                    <el-option label="钉钉" value="dingtalk" />
                    <el-option label="飞书" value="feishu" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="4">
                <el-form-item label="启用">
                  <el-switch v-model="form.enabled" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item label="标题模板">
              <el-input v-model="form.title_template" placeholder="如：代码评审 · {{project_name}}" />
            </el-form-item>

            <el-form-item label="正文模板">
              <el-input
                v-model="form.body_template"
                type="textarea"
                :rows="10"
                placeholder="支持 Markdown 和 {{变量}} 语法"
              />
            </el-form-item>

            <!-- 变量参考 -->
            <el-collapse style="margin-bottom: 16px">
              <el-collapse-item title="📌 可用变量参考（点击展开）" name="vars">
                <el-table :data="variableList" size="small" border>
                  <el-table-column prop="var" label="变量" width="200">
                    <template #default="{ row }">
                      <code style="cursor:pointer; color: #409eff" @click="copyVar(row.var)">
                        {{ row.var }}
                      </code>
                    </template>
                  </el-table-column>
                  <el-table-column prop="desc" label="说明" />
                  <el-table-column prop="example" label="示例值" width="180" />
                </el-table>
              </el-collapse-item>
            </el-collapse>

            <!-- 预览区 -->
            <el-divider content-position="left">实时预览</el-divider>

            <el-row :gutter="12" style="margin-bottom: 12px">
              <el-col :span="8">
                <el-input v-model="preview.mr_title" placeholder="MR 标题" size="small" />
              </el-col>
              <el-col :span="6">
                <el-input v-model="preview.mr_author" placeholder="作者" size="small" />
              </el-col>
              <el-col :span="6">
                <el-input v-model="preview.project_name" placeholder="项目名" size="small" />
              </el-col>
              <el-col :span="4">
                <el-button size="small" type="primary" @click="handlePreview" :loading="previewing">
                  渲染预览
                </el-button>
              </el-col>
            </el-row>
            <el-row :gutter="12" style="margin-bottom: 12px">
              <el-col :span="4">
                <el-input-number v-model="preview.critical_count" :min="0" size="small" placeholder="严重" style="width:100%" />
              </el-col>
              <el-col :span="4">
                <el-input-number v-model="preview.warning_count" :min="0" size="small" placeholder="警告" style="width:100%" />
              </el-col>
              <el-col :span="4">
                <el-input-number v-model="preview.suggestion_count" :min="0" size="small" placeholder="建议" style="width:100%" />
              </el-col>
              <el-col :span="4">
                <el-input-number v-model="preview.info_count" :min="0" size="small" placeholder="信息" style="width:100%" />
              </el-col>
            </el-row>

            <div v-if="previewResult" class="preview-box">
              <div class="preview-card">
                <div class="preview-title">{{ previewResult.title }}</div>
                <div class="preview-body" v-html="renderMarkdown(previewResult.body)" />
                <div class="preview-btn">查看 MR →</div>
              </div>
            </div>
          </el-form>
        </div>

        <el-empty v-else description="请从左侧选择或新增模板" style="margin-top: 60px" />
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getNotificationTemplates,
  createNotificationTemplate,
  updateNotificationTemplate,
  deleteNotificationTemplate,
  previewNotificationTemplate,
} from '@/api/notificationTemplates'

const channelNames = { dingtalk: '钉钉', feishu: '飞书' }
const channelColor = { dingtalk: '#0089FF', feishu: '#3370FF' }

const loading = ref(false)
const saving = ref(false)
const previewing = ref(false)
const templates = ref([])
const currentTemplate = ref(null)
const isCreating = ref(false)
const previewResult = ref(null)

const form = reactive({
  name: '',
  channel: 'dingtalk',
  title_template: '',
  body_template: '',
  description: '',
  enabled: true,
})

const preview = reactive({
  mr_title: 'feat: 新增用户登录功能',
  mr_author: 'zhangsan',
  project_name: 'backend-api',
  critical_count: 1,
  warning_count: 2,
  suggestion_count: 3,
  info_count: 0,
  summary: '本次 MR 发现 1 个严重问题，建议合并前修复。',
})

const variableList = [
  { var: '{{mr_title}}',       desc: 'MR 标题',        example: 'feat: 新增登录' },
  { var: '{{mr_author}}',      desc: '提交人',          example: 'zhangsan' },
  { var: '{{project_name}}',   desc: '项目名称',        example: 'backend-api' },
  { var: '{{critical_count}}', desc: '严重问题数',      example: '1' },
  { var: '{{warning_count}}',  desc: '警告数',          example: '2' },
  { var: '{{suggestion_count}}',desc: '建议数',         example: '3' },
  { var: '{{info_count}}',     desc: '信息数',          example: '0' },
  { var: '{{summary}}',        desc: 'AI 评审摘要',     example: '本次 MR 发现...' },
  { var: '{{mr_url}}',         desc: 'MR 链接',         example: 'https://...' },
  { var: '{{status_emoji}}',   desc: '状态图标（预计算）',  example: '⚠️ / 🔔 / ✅' },
  { var: '{{status_text}}',    desc: '状态文字（预计算）',  example: '发现严重问题' },
  { var: '{{status_color}}',   desc: '状态颜色（预计算）',  example: '#FF4D4F' },
]

const groupedTemplates = computed(() => {
  const groups = {}
  for (const tpl of templates.value) {
    if (!groups[tpl.channel]) groups[tpl.channel] = []
    groups[tpl.channel].push(tpl)
  }
  return groups
})

async function loadTemplates() {
  loading.value = true
  try {
    const res = await getNotificationTemplates()
    templates.value = res.data?.items || res.data || []
  } finally {
    loading.value = false
  }
}

function selectTemplate(tpl) {
  isCreating.value = false
  currentTemplate.value = tpl
  previewResult.value = null
  Object.assign(form, {
    name: tpl.name,
    channel: tpl.channel,
    title_template: tpl.title_template,
    body_template: tpl.body_template,
    description: tpl.description || '',
    enabled: tpl.enabled,
  })
}

function openCreate() {
  isCreating.value = true
  currentTemplate.value = { id: '__new__' }
  previewResult.value = null
  Object.assign(form, {
    name: '',
    channel: 'dingtalk',
    title_template: '代码评审 · {{project_name}}',
    body_template: '',
    description: '',
    enabled: true,
  })
}

async function handleSave() {
  if (!form.name || !form.title_template || !form.body_template) {
    ElMessage.warning('请填写模板名称、标题和正文')
    return
  }
  saving.value = true
  try {
    if (isCreating.value) {
      const res = await createNotificationTemplate({ ...form })
      ElMessage.success('创建成功')
      await loadTemplates()
      const created = templates.value.find(t => t.id === res.data?.id)
      if (created) selectTemplate(created)
    } else {
      await updateNotificationTemplate(currentTemplate.value.id, {
        name: form.name,
        title_template: form.title_template,
        body_template: form.body_template,
        description: form.description,
        enabled: form.enabled,
      })
      ElMessage.success('保存成功')
      await loadTemplates()
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  await ElMessageBox.confirm(`确定删除模板「${currentTemplate.value.name}」？`, '确认删除', {
    type: 'warning',
  })
  try {
    await deleteNotificationTemplate(currentTemplate.value.id)
    ElMessage.success('已删除')
    currentTemplate.value = null
    await loadTemplates()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

async function handlePreview() {
  if (!form.title_template || !form.body_template) {
    ElMessage.warning('请先填写标题和正文模板')
    return
  }
  // 未保存时先临时保存再预览，已保存则直接预览
  let templateId = currentTemplate.value?.id
  if (isCreating.value || !templateId || templateId === '__new__') {
    ElMessage.info('请先保存模板再预览')
    return
  }
  previewing.value = true
  try {
    const res = await previewNotificationTemplate(templateId, { ...preview })
    previewResult.value = res.data
  } catch (e) {
    ElMessage.error('预览失败')
  } finally {
    previewing.value = false
  }
}

function copyVar(varStr) {
  navigator.clipboard?.writeText(varStr)
  ElMessage.success(`已复制 ${varStr}`)
}

function renderMarkdown(text) {
  if (!text) return ''
  // 简单处理：转义 HTML，保留换行和加粗
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

onMounted(loadTemplates)
</script>

<style scoped>
.channel-group {
  margin-bottom: 12px;
}
.channel-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #909399;
  padding: 6px 8px 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.tpl-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
  margin-bottom: 2px;
}
.tpl-item:hover {
  background: #f5f7fa;
}
.tpl-item.active {
  background: #ecf5ff;
  color: #409eff;
}
.tpl-name {
  font-size: 13px;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-right: 8px;
}
.preview-box {
  margin-top: 8px;
}
.preview-card {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  max-width: 480px;
}
.preview-title {
  background: #f5f7fa;
  padding: 10px 16px;
  font-weight: 600;
  font-size: 14px;
  border-bottom: 1px solid #e4e7ed;
}
.preview-body {
  padding: 12px 16px;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
.preview-btn {
  text-align: center;
  padding: 10px;
  color: #409eff;
  font-size: 13px;
  border-top: 1px solid #e4e7ed;
  cursor: pointer;
}
</style>
