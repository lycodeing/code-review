<template>
  <el-dialog
    :model-value="visible"
    :title="isEdit ? '编辑模板' : '新增模板'"
    width="min(92vw, 1400px)"
    destroy-on-close
    @opened="onDialogOpened"
    @closed="onDialogClosed"
    @close="emit('close')"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
      <el-form-item label="模板名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入模板名称" />
      </el-form-item>

      <el-row :gutter="16">
        <el-col :span="8">
          <el-form-item label="类别" prop="category">
            <el-select v-model="form.category" placeholder="选择类别" style="width: 100%">
              <el-option label="默认" value="default" />
              <el-option label="Python" value="python" />
              <el-option label="Java" value="java" />
              <el-option label="Go" value="go" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="语言" prop="locale">
            <el-select v-model="form.locale" placeholder="选择语言" style="width: 100%">
              <el-option label="中文" value="zh" />
              <el-option label="English" value="en" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="启用状态">
            <el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" />
          </el-form-item>
        </el-col>
      </el-row>

      <!-- 分屏编辑区 -->
      <el-form-item label="模板内容" prop="content" class="editor-form-item">
        <div class="split-editor">
          <!-- 左侧：CodeMirror 编辑器 -->
          <div class="editor-pane">
            <div class="editor-toolbar">
              <span class="toolbar-label">编辑</span>
              <div class="toolbar-actions">
                <el-button size="small" type="primary" plain @click="insertText('{{diff}}')">
                  + <code>&#123;&#123;diff&#125;&#125;</code>
                </el-button>
                <el-button size="small" type="success" plain @click="insertText('{{files_context}}')">
                  + <code>&#123;&#123;files_context&#125;&#125;</code>
                </el-button>
                <span class="char-count" :class="{ 'count-warn': missingPlaceholders.length }">
                  {{ form.content.length }} 字符
                  <template v-if="missingPlaceholders.length">
                    · 缺少 {{ missingPlaceholders.join('、') }}
                  </template>
                </span>
              </div>
            </div>
            <div ref="editorContainer" class="cm-container" />
          </div>

          <!-- 右侧：Markdown 预览 -->
          <div class="preview-pane">
            <div class="editor-toolbar">
              <span class="toolbar-label">预览</span>
              <div class="toolbar-actions">
                <el-tag v-if="placeholderStatus.hasDiff" size="small" type="primary">✓ diff</el-tag>
                <el-tag v-else size="small" type="danger">✗ diff</el-tag>
                <el-tag v-if="placeholderStatus.hasFiles" size="small" type="success">✓ files_context</el-tag>
                <el-tag v-else size="small" type="danger">✗ files_context</el-tag>
                <el-divider direction="vertical" />
                <el-radio-group v-model="previewMode" size="small">
                  <el-radio-button label="rendered">渲染</el-radio-button>
                  <el-radio-button label="raw">原文</el-radio-button>
                </el-radio-group>
              </div>
            </div>
            <div
              v-if="form.content"
              class="preview-content"
              :class="{ 'raw-mode': previewMode === 'raw' }"
              v-html="renderedPreview"
            />
            <div v-else class="preview-empty">
              在左侧编写模板内容，此处将实时显示预览效果
            </div>
          </div>
        </div>
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
import { ref, reactive, computed, watch, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createTemplate, updateTemplate } from '@/api/templates'

// CodeMirror 6
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter, drawSelection } from '@codemirror/view'
import { EditorState } from '@codemirror/state'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { markdown } from '@codemirror/lang-markdown'
import { oneDark } from '@codemirror/theme-one-dark'
import { syntaxHighlighting, defaultHighlightStyle, bracketMatching } from '@codemirror/language'

// markdown-it 渲染
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({ breaks: true, linkify: true })

const props = defineProps({
  visible: Boolean,
  template: { type: Object, default: null }
})
const emit = defineEmits(['close', 'saved'])

const formRef = ref(null)
const editorContainer = ref(null)
const submitting = ref(false)
const previewMode = ref('rendered')
const isEdit = computed(() => !!props.template)

/** @type {EditorView | null} */
let editorView = null

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

// 占位符状态
const placeholderStatus = computed(() => ({
  hasDiff: form.content.includes('{{diff}}'),
  hasFiles: form.content.includes('{{files_context}}'),
}))

const missingPlaceholders = computed(() => {
  const missing = []
  if (!placeholderStatus.value.hasDiff) missing.push('{{diff}}')
  if (!placeholderStatus.value.hasFiles) missing.push('{{files_context}}')
  return missing
})

// 预览渲染
const renderedPreview = computed(() => {
  if (!form.content) return ''
  if (previewMode.value === 'raw') {
    // 原文模式：转义 HTML，高亮占位符
    const escaped = form.content
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
    return escaped
      .replace(/\{\{diff\}\}/g, '<mark class="ph-diff">{{diff}}</mark>')
      .replace(/\{\{files_context\}\}/g, '<mark class="ph-files">{{files_context}}</mark>')
      .replace(/\n/g, '<br>')
  }
  // 渲染模式：先高亮占位符再由 markdown-it 渲染
  const withMarkers = form.content
    .replace(/\{\{diff\}\}/g, '`__PH_DIFF__`')
    .replace(/\{\{files_context\}\}/g, '`__PH_FILES__`')
  const rendered = md.render(withMarkers)
  return rendered
    .replace(/`?__PH_DIFF__`?/g, '<mark class="ph-diff">{{diff}}</mark>')
    .replace(/`?__PH_FILES__`?/g, '<mark class="ph-files">{{files_context}}</mark>')
})

// 创建 CodeMirror 实例
function createEditor(initialContent) {
  if (!editorContainer.value) return

  const updateListener = EditorView.updateListener.of((update) => {
    if (update.docChanged) {
      form.content = update.state.doc.toString()
    }
  })

  const isDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches

  const state = EditorState.create({
    doc: initialContent,
    extensions: [
      lineNumbers(),
      highlightActiveLine(),
      highlightActiveLineGutter(),
      drawSelection(),
      bracketMatching(),
      history(),
      markdown(),
      syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
      keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
      isDark ? oneDark : [],
      EditorView.theme({
        '&': { height: '100%', fontSize: '13px' },
        '.cm-scroller': {
          fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
          lineHeight: '1.7',
          overflow: 'auto',
        },
        '.cm-content': { padding: '12px 0' },
        '.cm-gutters': { background: 'var(--el-fill-color-light)', borderRight: '1px solid var(--el-border-color-light)' },
      }),
      updateListener,
    ],
  })

  editorView = new EditorView({ state, parent: editorContainer.value })
}

function destroyEditor() {
  if (editorView) {
    editorView.destroy()
    editorView = null
  }
}

function setEditorContent(content) {
  if (!editorView) return
  const current = editorView.state.doc.toString()
  if (current === content) return
  editorView.dispatch({
    changes: { from: 0, to: current.length, insert: content }
  })
}

// 在光标位置插入文本
function insertText(text) {
  if (!editorView) return
  const { from, to } = editorView.state.selection.main
  editorView.dispatch({
    changes: { from, to, insert: text },
    selection: { anchor: from + text.length },
  })
  editorView.focus()
}

// 监听 template prop，填充表单
watch(
  () => props.template,
  (val) => {
    const content = val?.content || ''
    Object.assign(form, {
      name: val?.name || '',
      category: val?.category || 'default',
      locale: val?.locale || 'zh',
      enabled: val?.enabled ?? 1,
      content,
    })
    // 若编辑器已创建则同步内容
    if (editorView) setEditorContent(content)
  },
  { immediate: true }
)

// 对话框动画结束后初始化编辑器（此时 DOM 已完全渲染并有正确尺寸）
function onDialogOpened() {
  if (!editorView) {
    createEditor(form.content)
  }
}

// 对话框关闭动画结束后销毁编辑器
function onDialogClosed() {
  destroyEditor()
}

onUnmounted(() => {
  destroyEditor()
})

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  if (missingPlaceholders.value.length) {
    await ElMessageBox.confirm(
      `模板中缺少以下占位符：${missingPlaceholders.value.join('、')}，评审时相关内容将无法注入，确认保存吗？`,
      '占位符缺失',
      { confirmButtonText: '仍然保存', cancelButtonText: '返回编辑', type: 'warning' }
    ).catch(() => { throw new Error('cancel') })
  }

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
  } catch (e) {
    if (e?.message !== 'cancel') throw e
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.editor-form-item :deep(.el-form-item__content) {
  display: block;
}

.split-editor {
  display: flex;
  gap: 12px;
  width: 100%;
  height: 560px;
}

.editor-pane,
.preview-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  overflow: hidden;
  min-width: 0;
}

.editor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color-light);
  flex-shrink: 0;
  gap: 8px;
  flex-wrap: wrap;
}

.toolbar-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  flex-shrink: 0;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.toolbar-actions code {
  font-size: 11px;
  background: var(--el-fill-color);
  padding: 1px 3px;
  border-radius: 3px;
}

.char-count {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  white-space: nowrap;
}

.char-count.count-warn {
  color: var(--el-color-warning);
}

/* CodeMirror 容器 */
.cm-container {
  flex: 1;
  overflow: hidden;
  background: var(--el-bg-color);
}

.cm-container :deep(.cm-editor) {
  height: 100%;
}

.cm-container :deep(.cm-editor.cm-focused) {
  outline: none;
}

/* 预览区 */
.preview-content {
  flex: 1;
  padding: 16px;
  font-size: 14px;
  line-height: 1.8;
  color: var(--el-text-color-primary);
  background: var(--el-bg-color);
  overflow-y: auto;
  word-break: break-word;
}

.preview-content.raw-mode {
  font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
  font-size: 13px;
  white-space: pre-wrap;
}

/* Markdown 样式 */
.preview-content :deep(h1),
.preview-content :deep(h2),
.preview-content :deep(h3) {
  margin: 0.8em 0 0.4em;
  font-weight: 600;
}

.preview-content :deep(p) {
  margin: 0.5em 0;
}

.preview-content :deep(ul),
.preview-content :deep(ol) {
  padding-left: 1.5em;
  margin: 0.5em 0;
}

.preview-content :deep(code) {
  background: var(--el-fill-color);
  padding: 2px 5px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
}

.preview-content :deep(pre) {
  background: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
}

.preview-content :deep(pre code) {
  background: none;
  padding: 0;
}

.preview-content :deep(blockquote) {
  border-left: 4px solid var(--el-border-color);
  margin: 0.5em 0;
  padding: 0 1em;
  color: var(--el-text-color-secondary);
}

.preview-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-placeholder);
  font-size: 13px;
  font-style: italic;
  padding: 24px;
  text-align: center;
}

/* 占位符高亮徽章 */
:deep(.ph-diff) {
  background: #dbeafe;
  color: #1d4ed8;
  border: 1px solid #93c5fd;
  border-radius: 4px;
  padding: 1px 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-style: normal;
  white-space: nowrap;
}

:deep(.ph-files) {
  background: #dcfce7;
  color: #15803d;
  border: 1px solid #86efac;
  border-radius: 4px;
  padding: 1px 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-style: normal;
  white-space: nowrap;
}
</style>
