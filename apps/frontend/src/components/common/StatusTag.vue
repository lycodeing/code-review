<template>
  <el-tag
    :type="statusMap[status]?.type || 'info'"
    effect="dark"
    size="small"
    :class="statusClass"
  >
    <el-icon v-if="status === 'in_progress'" class="status-spin"><Loading /></el-icon>
    <span v-if="status === 'completed'" class="status-check">&#10003;</span>
    {{ statusMap[status]?.label || status }}
  </el-tag>
</template>

<script setup>
import { computed } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { severityMap, reviewStatusMap } from '@/utils/format'

const props = defineProps({
  status: { type: String, required: true },
  type: { type: String, default: 'review' } // review | severity
})

const statusMap = props.type === 'severity' ? severityMap : reviewStatusMap

const statusClass = computed(() => ({
  'status-tag--progress': props.status === 'in_progress',
  'status-tag--completed': props.status === 'completed',
}))
</script>

<style scoped>
.status-tag--progress {
  animation: pulse-opacity 1.5s ease-in-out infinite;
}

.status-tag--completed {
  animation: completed-pop 0.4s ease-out;
}

.status-spin {
  animation: spin 1s linear infinite;
  margin-right: 2px;
  font-size: 12px;
}

.status-check {
  margin-right: 2px;
  font-weight: 700;
  animation: check-in 0.3s ease-out;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes pulse-opacity {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

@keyframes completed-pop {
  0% { transform: scale(0.8); opacity: 0; }
  60% { transform: scale(1.1); }
  100% { transform: scale(1); opacity: 1; }
}

@keyframes check-in {
  0% { transform: scale(0); opacity: 0; }
  60% { transform: scale(1.3); }
  100% { transform: scale(1); opacity: 1; }
}
</style>
