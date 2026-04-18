<template>
  <div class="page-container">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-cards">
      <el-col :xs="12" :sm="6" v-for="card in statCards" :key="card.key">
        <div class="stat-card" :style="{ borderTopColor: card.color }">
          <div class="stat-info">
            <div class="stat-value">{{ card.value }}</div>
            <div class="stat-label">{{ card.label }}</div>
          </div>
          <div class="stat-icon" :style="{ background: card.color + '18', color: card.color }">
            <el-icon :size="28"><component :is="card.icon" /></el-icon>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <!-- 评审趋势图 -->
      <el-col :xs="24" :lg="16">
        <div class="chart-card">
          <div class="card-header">
            <span class="card-title">评审趋势</span>
          </div>
          <div class="chart-wrapper">
            <v-chart :option="trendOption" autoresize style="height: 320px" />
          </div>
        </div>
      </el-col>

      <!-- 最近评审 -->
      <el-col :xs="24" :lg="8">
        <div class="chart-card">
          <div class="card-header">
            <span class="card-title">最近评审</span>
            <el-button text type="primary" @click="$router.push('/reviews')">
              查看全部
            </el-button>
          </div>
          <div class="recent-list">
            <div
              v-for="item in recentReviews"
              :key="item.id"
              class="recent-item"
              @click="$router.push(`/reviews/${item.id}`)"
            >
              <div class="recent-info">
                <div class="recent-title">{{ item.mr_title }}</div>
                <div class="recent-meta">
                  {{ item.mr_author }} · {{ formatDateTime(item.created_at) }}
                </div>
              </div>
              <StatusTag :status="item.status" />
            </div>
            <el-empty v-if="!recentReviews.length" description="暂无评审记录" :image-size="60" />
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 系统状态 -->
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="24">
        <div class="chart-card">
          <div class="card-header">
            <span class="card-title">系统状态</span>
            <el-button text type="primary" :loading="healthLoading" @click="checkHealth">
              刷新
            </el-button>
          </div>
          <div class="health-grid">
            <div class="health-item" v-for="(value, key) in healthData" :key="key">
              <el-icon :size="24" :color="value ? '#67C23A' : '#F56C6C'">
                <CircleCheckFilled v-if="value" />
                <CircleCloseFilled v-else />
              </el-icon>
              <span class="health-label">{{ healthLabels[key] || key }}</span>
              <el-tag :type="value ? 'success' : 'danger'" size="small">
                {{ value ? '正常' : '异常' }}
              </el-tag>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent
} from 'echarts/components'
import { getReviews } from '@/api/reviews'
import { getProjects } from '@/api/projects'
import { formatDateTime } from '@/utils/format'
import StatusTag from '@/components/common/StatusTag.vue'
import axios from 'axios'

use([CanvasRenderer, LineChart, PieChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent])

// 统计卡片
const projects = ref([])
const reviews = ref([])
const recentReviews = ref([])

const statCards = computed(() => {
  const completed = reviews.value.filter((r) => r.status === 'completed').length
  const failed = reviews.value.filter((r) => r.status === 'failed').length
  return [
    { key: 'projects', label: '项目总数', value: projects.value.length, icon: 'FolderOpened', color: '#409EFF' },
    { key: 'reviews', label: '评审总数', value: reviews.value.length, icon: 'Document', color: '#67C23A' },
    { key: 'completed', label: '已完成', value: completed, icon: 'CircleCheck', color: '#E6A23C' },
    { key: 'failed', label: '失败数', value: failed, icon: 'CircleClose', color: '#F56C6C' }
  ]
})

// 评审趋势图配置
const trendOption = computed(() => {
  // 按日期聚合
  const dateMap = {}
  reviews.value.forEach((r) => {
    const date = r.created_at?.split('T')[0] || '未知'
    dateMap[date] = (dateMap[date] || 0) + 1
  })

  const dates = Object.keys(dateMap).sort().slice(-14)
  const values = dates.map((d) => dateMap[d])

  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 20, bottom: 30 },
    xAxis: {
      type: 'category',
      data: dates.map((d) => d.slice(5)),
      axisLine: { lineStyle: { color: '#e6e6e6' } },
      axisLabel: { color: '#909399' }
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#f0f0f0' } },
      axisLabel: { color: '#909399' }
    },
    series: [{
      type: 'line',
      data: values,
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { width: 2, color: '#409EFF' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(64,158,255,0.3)' },
            { offset: 1, color: 'rgba(64,158,255,0.02)' }
          ]
        }
      },
      itemStyle: { color: '#409EFF' }
    }]
  }
})

// 系统健康状态
const healthLoading = ref(false)
const healthData = ref({})
const healthLabels = { database: '数据库', notifications: '通知服务' }

async function checkHealth() {
  healthLoading.value = true
  try {
    const res = await axios.get('/api/v1/health')
    healthData.value = res.checks || res
  } catch {
    healthData.value = { database: false, notifications: false }
  } finally {
    healthLoading.value = false
  }
}

// 加载仪表盘数据
async function loadDashboard() {
  try {
    const [projRes, revRes] = await Promise.all([
      getProjects(),
      getReviews({ limit: 100 })
    ])
    projects.value = Array.isArray(projRes) ? projRes : []
    reviews.value = Array.isArray(revRes) ? revRes : []
    recentReviews.value = reviews.value.slice(0, 8)
  } catch {
    // 静默处理
  }
  checkHealth()
}

onMounted(loadDashboard)
</script>

<style lang="scss" scoped>
.stat-cards {
  .el-col {
    margin-bottom: 0;
  }
}

.stat-card {
  background: $card-bg;
  border-radius: $border-radius;
  padding: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 3px solid;
  box-shadow: $card-shadow;
  transition: transform 0.2s;

  &:hover {
    transform: translateY(-2px);
  }
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chart-card {
  background: $card-bg;
  border-radius: $border-radius;
  box-shadow: $card-shadow;
  padding: 20px;
  height: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.chart-wrapper {
  min-height: 300px;
}

.recent-list {
  max-height: 340px;
  overflow-y: auto;
}

.recent-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background 0.15s;

  &:hover {
    background: #fafafa;
    margin: 0 -12px;
    padding: 12px;
    border-radius: 4px;
  }

  &:last-child {
    border-bottom: none;
  }
}

.recent-title {
  font-size: 14px;
  color: #303133;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recent-meta {
  font-size: 12px;
  color: #c0c4cc;
  margin-top: 4px;
}

.health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.health-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px;
  background: #fafafa;
  border-radius: $border-radius;
}

.health-label {
  flex: 1;
  font-size: 14px;
  color: #606266;
}
</style>
