<template>
  <div class="comment-item">
    <div class="comment-header">
      <div v-if="showFile" class="comment-file">
        <el-icon><Document /></el-icon>
        <span>{{ comment.file_path }}</span>
      </div>
      <div class="comment-meta">
        <StatusTag :status="comment.severity" type="severity" />
        <span v-if="comment.line_start" class="line-range">
          L{{ comment.line_start }}{{ comment.line_end !== comment.line_start ? ` - L${comment.line_end}` : '' }}
        </span>
      </div>
    </div>
    <div class="comment-body md-content" v-html="renderMarkdown(comment.message)" />
    <div v-if="comment.suggestion" class="comment-suggestion">
      <strong>建议修复：</strong>
      <div class="md-content" v-html="renderMarkdown(comment.suggestion)" />
    </div>
    <div v-if="showFeedback" class="comment-feedback">
      <el-button text size="small" :type="comment.feedback === 'thumbs_up' ? 'primary' : ''" @click="emit('feedback', comment, 'thumbs_up')">👍 有用</el-button>
      <el-button text size="small" :type="comment.feedback === 'thumbs_down' ? 'danger' : ''" @click="emit('feedback', comment, 'thumbs_down')">👎 无用</el-button>
    </div>
  </div>
</template>

<script setup>
import { Document } from '@element-plus/icons-vue'
import { renderMarkdown } from '@/utils/markdown'
import StatusTag from '@/components/common/StatusTag.vue'

defineProps({
  comment: { type: Object, required: true },
  showFile: { type: Boolean, default: true },
  showFeedback: { type: Boolean, default: true }
})

const emit = defineEmits(['feedback'])
</script>

<style lang="scss" scoped>
.comment-item {
  padding: 16px;
  border: 1px solid #ebeef5;
  border-radius: $border-radius;
  margin-bottom: 12px;
  transition: box-shadow 0.2s;

  &:hover {
    box-shadow: $card-shadow;
  }
}

.comment-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.comment-file {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #303133;
  font-family: monospace;
}

.comment-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.line-range {
  font-size: 12px;
  color: #909399;
  font-family: monospace;
}

.comment-body {
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
}

.md-content {
  font-size: 14px;
  line-height: 1.7;

  :deep(p) { margin: 4px 0; }
  :deep(ul), :deep(ol) { padding-left: 20px; margin: 6px 0; }
  :deep(li) { margin: 2px 0; }
  :deep(strong) { font-weight: 600; }
  :deep(code) {
    background: #f5f5f5;
    color: #1a1a1a;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: monospace;
    font-size: 13px;
    border: 1px solid #d0d0d0;
  }
  :deep(.hljs-block) {
    margin: 8px 0;
    border-radius: 6px;
    overflow: hidden;
    code {
      display: block;
      padding: 12px;
      font-size: 13px;
      line-height: 1.5;
      overflow-x: auto;
      background: transparent;
    }
  }
}

.comment-suggestion {
  margin-top: 10px;
  padding: 10px 12px;
  background: #f0f9eb;
  border-radius: 4px;
  font-size: 13px;

  strong {
    color: #67C23A;
    display: block;
    margin-bottom: 6px;
  }
}
</style>
