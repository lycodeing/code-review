<template>
  <el-tag :type="statusMap[status]?.type || 'info'" effect="dark" size="small">
    {{ statusMap[status]?.label || status }}
  </el-tag>
</template>

<script setup>
import { severityMap, reviewStatusMap } from '@/utils/format'

const props = defineProps({
  status: { type: String, required: true },
  type: { type: String, default: 'review' } // review | severity
})

const statusMap = props.type === 'severity' ? severityMap : reviewStatusMap
</script>
