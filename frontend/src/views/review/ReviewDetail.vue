<template>
  <div class="page-container">
    <el-page-header @back="$router.push('/reviews')" title="返回列表">
      <template #content>
        <span>评审详情</span>
        <StatusTag v-if="detail.status" :status="detail.status" style="margin-left: 8px" />
      </template>
    </el-page-header>

    <div v-loading="loading" style="margin-top: 20px">
      <!-- 基本信息 -->
      <el-card shadow="never" class="detail-card">
        <template #header>
          <span class="card-title">{{ detail.mr_title || '加载中...' }}</span>
        </template>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="MR 标题">{{ detail.mr_title }}</el-descriptions-item>
          <el-descriptions-item label="作者">{{ detail.mr_author }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <StatusTag v-if="detail.status" :status="detail.status" />
          </el-descriptions-item>
          <el-descriptions-item label="源分支">{{ detail.source_branch }}</el-descriptions-item>
          <el-descriptions-item label="目标分支">{{ detail.target_branch }}</el-descriptions-item>
          <el-descriptions-item label="触发方式">{{ detail.trigger_action }}</el-descriptions-item>
          <el-descriptions-item label="LLM 模型">{{ detail.model_name }}</el-descriptions-item>
          <el-descriptions-item label="评论数">{{ detail.total_comments }}</el-descriptions-item>
          <el-descriptions-item label="严重/警告">{{ detail.critical_count }} / {{ detail.warning_count }}</el-descriptions-item>
          <el-descriptions-item label="MR 链接">
            <a v-if="detail.mr_url" :href="detail.mr_url" target="_blank" class="link-text">
              {{ detail.mr_url }}
            </a>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDateTime(detail.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ formatDateTime(detail.completed_at) }}</el-descriptions-item>
        </el-descriptions>

        <!-- 评审摘要 -->
        <div v-if="detail.summary" class="summary-section">
          <h4>评审摘要</h4>
          <div class="summary-content">{{ detail.summary }}</div>
        </div>

        <!-- 错误信息 -->
        <el-alert
          v-if="detail.error_message"
          type="error"
          :title="detail.error_message"
          show-icon
          style="margin-top: 16px"
        />
      </el-card>

      <!-- 评论列表 -->
      <el-card shadow="never" class="detail-card" style="margin-top: 16px">
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center">
            <span class="card-title">评审评论 ({{ comments.length }})</span>
          </div>
        </template>

        <div v-if="comments.length">
          <div v-for="comment in comments" :key="comment.id" class="comment-item">
            <div class="comment-header">
              <div class="comment-file">
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
            <div class="comment-body">{{ comment.message }}</div>
            <div v-if="comment.suggestion" class="comment-suggestion">
              <strong>建议修复：</strong>
              <pre>{{ comment.suggestion }}</pre>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无评论" />
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getReview, getReviewComments } from '@/api/review'
import { formatDateTime } from '@/utils/format'
import StatusTag from '@/components/common/StatusTag.vue'

const route = useRoute()
const loading = ref(true)
const detail = ref({})
const comments = ref([])

async function loadDetail() {
  loading.value = true
  try {
    const id = route.params.id
    const [taskData, commentsData] = await Promise.all([
      getReview(id),
      getReviewComments(id)
    ])
    detail.value = taskData
    comments.value = Array.isArray(commentsData) ? commentsData : []
  } catch {
    // 拦截器已处理
  } finally {
    loading.value = false
  }
}

onMounted(loadDetail)
</script>

<style lang="scss" scoped>
.detail-card {
  border-radius: $border-radius;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.link-text {
  color: $primary-color;
  word-break: break-all;
}

.summary-section {
  margin-top: 20px;

  h4 {
    font-size: 14px;
    color: #303133;
    margin-bottom: 8px;
  }
}

.summary-content {
  background: #f5f7fa;
  padding: 12px 16px;
  border-radius: $border-radius;
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
  white-space: pre-wrap;
}

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
  white-space: pre-wrap;
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

  pre {
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 10px;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 13px;
    line-height: 1.5;
  }
}
</style>
