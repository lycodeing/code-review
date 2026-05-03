<template>
  <el-drawer
    :model-value="visible"
    title="调用详情"
    :size="size"
    direction="rtl"
    @update:model-value="emit('update:visible', $event)"
  >
    <div v-if="log">
      <el-descriptions :column="2" border size="small" style="margin-bottom: 16px">
        <el-descriptions-item label="类型">
          <el-tag :type="callTypeMap[log.call_type]?.type || 'info'" size="small">
            {{ callTypeMap[log.call_type]?.label || log.call_type }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="提供商">{{ log.provider }}</el-descriptions-item>
        <el-descriptions-item label="结果">
          <el-tag :type="callLogStatusMap[log.status]?.type || 'info'" size="small">
            {{ callLogStatusMap[log.status]?.label || log.status }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="HTTP状态码">{{ log.response_status ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="耗时">{{ log.duration_ms ?? '-' }} ms</el-descriptions-item>
        <el-descriptions-item label="时间">{{ formatDateTime(log.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="URL" :span="2">
          <span style="word-break: break-all; font-family: monospace; font-size: 12px">
            {{ log.url || '-' }}
          </span>
        </el-descriptions-item>
        <el-descriptions-item v-if="log.error_message" label="错误信息" :span="2">
          <span style="color: #F56C6C; white-space: pre-wrap">{{ log.error_message }}</span>
        </el-descriptions-item>
      </el-descriptions>

      <el-collapse v-model="activeItems" style="margin-top: 8px">
        <el-collapse-item title="请求头" name="req_headers">
          <pre class="json-block">{{ formatJson(log.request_headers) }}</pre>
        </el-collapse-item>
        <el-collapse-item title="请求体" name="req_body">
          <pre class="json-block">{{ formatJson(log.request_body) }}</pre>
        </el-collapse-item>
        <el-collapse-item title="响应内容" name="resp_body">
          <pre class="json-block">{{ formatJson(log.response_body) }}</pre>
        </el-collapse-item>
      </el-collapse>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref } from 'vue'
import { formatDateTime, formatJson, callLogStatusMap, callTypeMap } from '@/utils/format'

defineProps({
  visible: { type: Boolean, required: true },
  log: { type: Object, default: null },
  size: { type: String, default: '620px' }
})

const emit = defineEmits(['update:visible'])

const activeItems = ref(['req_headers', 'req_body', 'resp_body'])
</script>

<style lang="scss" scoped>
.json-block {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 400px;
  overflow-y: auto;
}
</style>
