<template>
  <div class="tpl-page">
    <!-- 左侧列表 -->
    <div class="tpl-sidebar">
      <div class="tpl-sidebar-header">
        <span class="tpl-sidebar-title">通知模板</span>
        <el-button type="primary" size="small" @click="openCreate">
          <el-icon><Plus /></el-icon> 新增
        </el-button>
      </div>

      <el-scrollbar class="tpl-sidebar-body">
        <div v-if="loading" class="tpl-loading">
          <el-skeleton :rows="4" animated />
        </div>
        <template v-else>
          <div class="channel-group" v-for="(group, channel) in groupedTemplates" :key="channel">
            <div class="channel-label">
              <el-icon :color="channelColors[channel]"><Bell /></el-icon>
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
          <el-empty v-if="!templates.length" description="暂无模板" :image-size="60" style="padding: 40px 0" />
        </template>
      </el-scrollbar>
    </div>

    <!-- 右侧编辑 -->
    <div class="tpl-main">
      <template v-if="currentTemplate">
        <div class="tpl-main-header" v-loading="saving">
          <span class="tpl-main-title">{{ isCreating ? '新增模板' : currentTemplate.name }}</span>
          <div class="tpl-main-actions">
            <el-button
              v-if="!isCreating && !currentTemplate.is_default"
              type="danger"
              size="default"
              plain
              @click="handleDelete"
            >
              <el-icon><Delete /></el-icon> 删除
            </el-button>
            <el-button type="primary" size="default" @click="handleSave" :loading="saving">
              <el-icon><Check /></el-icon> 保存
            </el-button>
          </div>
        </div>

        <el-scrollbar class="tpl-main-body">
          <div class="tpl-form-wrap">
            <el-form :model="form" label-width="90px" size="default">
              <!-- 基础信息 -->
              <el-row :gutter="20">
                <el-col :span="10">
                  <el-form-item label="模板名称" required>
                    <el-input v-model="form.name" placeholder="请输入模板名称" />
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="渠道">
                    <el-select v-model="form.channel" :disabled="!isCreating" style="width: 100%">
                      <el-option
                        v-for="item in imChannelOptions"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="6">
                  <el-form-item label="启用">
                    <el-switch v-model="form.enabled" />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-form-item label="标题模板" required>
                <el-input v-model="form.title_template" placeholder="如：代码评审 · {{project_name}}" />
              </el-form-item>

              <el-form-item label="正文模板" required>
                <el-input
                  v-model="form.body_template"
                  type="textarea"
                  :rows="14"
                  placeholder="支持 Markdown 和 {{变量}} 语法"
                  style="font-family: monospace; font-size: 13px"
                />
              </el-form-item>

              <!-- 变量参考 -->
              <el-collapse style="margin-bottom: 20px; border-radius: 6px; overflow: hidden">
                <el-collapse-item name="vars">
                  <template #title>
                    <span style="font-size: 13px; color: #606266">📌 可用变量参考（点击展开）</span>
                  </template>
                  <el-table :data="variableList" size="small" border>
                    <el-table-column prop="var" label="变量" width="220">
                      <template #default="{ row }">
                        <code
                          style="cursor: pointer; color: #409eff; font-size: 12px"
                          @click="copyVar(row.var)"
                          :title="'点击复制 ' + row.var"
                        >{{ row.var }}</code>
                      </template>
                    </el-table-column>
                    <el-table-column prop="desc" label="说明" min-width="120" />
                    <el-table-column prop="example" label="示例值" width="200" />
                  </el-table>
                </el-collapse-item>
              </el-collapse>

              <!-- 预览区 -->
              <el-divider content-position="left">
                <span style="font-size: 13px; color: #606266">实时预览</span>
              </el-divider>

              <el-row :gutter="12" style="margin-bottom: 12px">
                <el-col :span="9">
                  <el-input v-model="preview.mr_title" placeholder="MR 标题" size="default" clearable />
                </el-col>
                <el-col :span="6">
                  <el-input v-model="preview.mr_author" placeholder="作者" size="default" clearable />
                </el-col>
                <el-col :span="6">
                  <el-input v-model="preview.project_name" placeholder="项目名" size="default" clearable />
                </el-col>
                <el-col :span="3">
                  <el-button style="width:100%" type="primary" @click="handlePreview" :loading="previewing">
                    预览
                  </el-button>
                </el-col>
              </el-row>

              <el-row :gutter="12" style="margin-bottom: 20px">
                <el-col :span="6">
                  <div class="count-input-wrap">
                    <span class="count-label">🔴 严重</span>
                    <el-input-number v-model="preview.critical_count" :min="0" size="default" controls-position="right" style="width: 100%" />
                  </div>
                </el-col>
                <el-col :span="6">
                  <div class="count-input-wrap">
                    <span class="count-label">🟡 警告</span>
                    <el-input-number v-model="preview.warning_count" :min="0" size="default" controls-position="right" style="width: 100%" />
                  </div>
                </el-col>
                <el-col :span="6">
                  <div class="count-input-wrap">
                    <span class="count-label">🔵 建议</span>
                    <el-input-number v-model="preview.suggestion_count" :min="0" size="default" controls-position="right" style="width: 100%" />
                  </div>
                </el-col>
                <el-col :span="6">
                  <div class="count-input-wrap">
                    <span class="count-label">ℹ️ 信息</span>
                    <el-input-number v-model="preview.info_count" :min="0" size="default" controls-position="right" style="width: 100%" />
                  </div>
                </el-col>
              </el-row>

              <div v-if="previewResult" class="preview-box">
                <div class="preview-label">渲染结果</div>
                <div class="preview-card">
                  <div class="preview-title">{{ previewResult.title }}</div>
                  <div class="preview-body" v-html="renderMarkdown(previewResult.body)" />
                  <div class="preview-btn">
                    <span class="preview-btn-inner">查看完整评审 →</span>
                  </div>
                </div>
              </div>
              <div v-else-if="!isCreating" class="preview-placeholder">
                填写预览参数后点击「预览」查看渲染效果
              </div>
            </el-form>
          </div>
        </el-scrollbar>
      </template>

      <div v-else class="tpl-empty">
        <el-empty description="请从左侧选择模板，或点击「新增」创建" :image-size="100" />
      </div>
    </div>
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
import { channelNames, channelColors, mapToOptions } from '@/utils/format'

const imChannelOptions = mapToOptions(channelNames).filter(item => item.value !== 'email')

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
  { var: '{{mr_title}}',        desc: 'MR 标题',                    example: 'feat: 新增登录' },
  { var: '{{mr_author}}',       desc: '提交人',                      example: 'zhangsan' },
  { var: '{{project_name}}',    desc: '项目名称',                    example: 'backend-api' },
  { var: '{{mr_url}}',          desc: 'MR 链接',                    example: 'https://gitee.com/.../pulls/1' },
  { var: '{{critical_count}}',  desc: '严重问题数',                  example: '1' },
  { var: '{{warning_count}}',   desc: '警告数',                      example: '2' },
  { var: '{{suggestion_count}}',desc: '建议数',                      example: '3' },
  { var: '{{info_count}}',      desc: '信息数',                      example: '0' },
  { var: '{{summary}}',         desc: 'AI 评审摘要（纯文本）',       example: '共 3 条评审意见：🔴 严重 0 · ...' },
  { var: '{{status_emoji}}',    desc: '状态图标（严重=⚠️ 警告=🔔 正常=✅）', example: '✅' },
  { var: '{{status_text}}',     desc: '状态文字（严重/警告/正常）',  example: '代码质量良好' },
  { var: '{{status_color}}',    desc: '状态颜色（严重=#FF4D4F 警告=#FA8C16 正常=#52C41A）', example: '#52C41A' },
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
    templates.value = Array.isArray(res) ? res : (res?.items || [])
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
    title_template: '{{status_emoji}} 代码评审 · {{project_name}}',
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
      const created = templates.value.find(t => t.id === res?.id)
      if (created) {
        selectTemplate(created)
      } else {
        isCreating.value = false
        currentTemplate.value = res
      }
    } else {
      const savedId = currentTemplate.value.id
      await updateNotificationTemplate(savedId, {
        name: form.name,
        title_template: form.title_template,
        body_template: form.body_template,
        description: form.description,
        enabled: form.enabled,
      })
      ElMessage.success('保存成功')
      await loadTemplates()
      const updated = templates.value.find(t => t.id === savedId)
      if (updated) selectTemplate(updated)
    }
  } catch (e) {
    const msg = e?.response?.data?.detail
      || (Array.isArray(e?.response?.data) ? JSON.stringify(e.response.data) : null)
      || e?.message
      || '保存失败'
    ElMessage.error(msg)
    console.error('保存失败', e?.response?.data || e)
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
  const templateId = currentTemplate.value?.id
  if (isCreating.value || !templateId || templateId === '__new__') {
    ElMessage.info('请先保存模板再预览')
    return
  }
  previewing.value = true
  try {
    const params = {
      ...preview,
      critical_count: preview.critical_count ?? 0,
      warning_count: preview.warning_count ?? 0,
      suggestion_count: preview.suggestion_count ?? 0,
      info_count: preview.info_count ?? 0,
    }
    const res = await previewNotificationTemplate(templateId, params)
    previewResult.value = res
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '预览失败'
    ElMessage.error(msg)
    console.error('预览失败', e?.response?.data || e)
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
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

onMounted(loadTemplates)
</script>

<style scoped>
.tpl-page {
  display: flex;
  height: calc(100vh - 56px - 32px); /* 减去 header + content padding */
  gap: 16px;
  overflow: hidden;
}

/* 左侧 */
.tpl-sidebar {
  width: 240px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}
.tpl-sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}
.tpl-sidebar-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}
.tpl-sidebar-body {
  flex: 1;
  overflow: hidden;
}
.tpl-loading {
  padding: 16px;
}

.channel-group {
  margin-bottom: 4px;
}
.channel-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 700;
  color: #909399;
  padding: 10px 16px 4px;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}
.tpl-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 16px;
  cursor: pointer;
  transition: background 0.15s;
  margin: 0 8px 2px;
  border-radius: 6px;
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

/* 右侧 */
.tpl-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}
.tpl-main-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 24px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}
.tpl-main-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}
.tpl-main-actions {
  display: flex;
  gap: 8px;
}
.tpl-main-body {
  flex: 1;
  overflow: hidden;
}
.tpl-form-wrap {
  padding: 24px;
}
.tpl-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 数量输入 */
.count-input-wrap {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.count-label {
  font-size: 12px;
  color: #909399;
}

/* 预览 */
.preview-placeholder {
  color: #c0c4cc;
  font-size: 13px;
  text-align: center;
  padding: 20px 0 8px;
}
.preview-box {
  margin-top: 4px;
}
.preview-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
}
.preview-card {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  max-width: 560px;
}
.preview-title {
  background: #f5f7fa;
  padding: 12px 18px;
  font-weight: 600;
  font-size: 14px;
  border-bottom: 1px solid #e4e7ed;
}
.preview-body {
  padding: 14px 18px;
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}
.preview-btn {
  display: flex;
  justify-content: center;
  padding: 12px 18px;
  border-top: 1px solid #e4e7ed;
  background: #fafafa;
}
.preview-btn-inner {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 24px;
  border-radius: 6px;
  border: 1px solid #409eff;
  color: #409eff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.preview-btn:hover .preview-btn-inner {
  background: #409eff;
  color: #fff;
}
</style>
