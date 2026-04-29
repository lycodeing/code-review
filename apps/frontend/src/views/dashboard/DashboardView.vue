<template>
  <div class="page-container">
    <!-- 周期切换 -->
    <div class="period-bar">
      <el-radio-group v-model="period" size="small" @change="loadStats">
        <el-radio-button value="week">本周</el-radio-button>
        <el-radio-button value="month">本月</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-cards">
      <el-col :xs="12" :sm="4" v-for="card in statCards" :key="card.key">
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
            <el-radio-group v-model="trendDays" size="small" @change="loadTrend">
              <el-radio-button :value="7">7天</el-radio-button>
              <el-radio-button :value="14">14天</el-radio-button>
              <el-radio-button :value="30">30天</el-radio-button>
            </el-radio-group>
          </div>
          <div class="chart-wrapper">
            <v-chart :option="trendOption" autoresize style="height: 320px" />
          </div>
        </div>
      </el-col>

      <!-- 严重程度分布 -->
      <el-col :xs="24" :lg="8">
        <div class="chart-card">
          <div class="card-header">
            <span class="card-title">严重程度分布</span>
          </div>
          <div class="chart-wrapper">
            <v-chart :option="severityOption" autoresize style="height: 320px" />
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <!-- 项目排行 -->
      <el-col :xs="24" :lg="12">
        <div class="chart-card">
          <div class="card-header">
            <span class="card-title">项目评审排行 Top 5</span>
          </div>
          <div class="rank-list">
            <div v-for="(item, idx) in topProjects" :key="item.project_id" class="rank-item">
              <span class="rank-index" :class="{ 'rank-top': idx < 3 }">{{ idx + 1 }}</span>
              <span class="rank-name">{{ item.project_name }}</span>
              <div class="rank-bar-wrapper">
                <div class="rank-bar" :style="{ width: rankBarWidth(item.review_count) + '%' }" />
              </div>
              <span class="rank-count">{{ item.review_count }}</span>
            </div>
            <el-empty v-if="!topProjects.length" description="暂无数据" :image-size="60" />
          </div>
        </div>
      </el-col>

      <!-- 最近评审 -->
      <el-col :xs="24" :lg="12">
        <div class="chart-card">
          <div class="card-header">
            <span class="card-title">最近评审</span>
            <el-button text type="primary" @click="$router.push('/reviews')">查看全部</el-button>
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
                <div class="recent-meta">{{ item.mr_author }} · {{ formatDateTime(item.created_at) }}</div>
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
            <el-button text type="primary" :loading="healthLoading" @click="checkHealth">刷新</el-button>
          </div>
          <div class="health-grid">
            <div class="health-item" v-for="(value, key) in healthData" :key="key">
              <el-icon :size="24" :color="value ? '#67C23A' : '#F56C6C'">
                <CircleCheckFilled v-if="value" />
                <CircleCloseFilled v-else />
              </el-icon>
              <span class="health-label">{{ healthLabels[key] || key }}</span>
              <el-tag :type="value ? 'success' : 'danger'" size="small">{{ value ? '正常' : '异常' }}</el-tag>
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
import { LineChart, PieChart, BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent
} from 'echarts/components'
import { getDashboardStats, getDashboardTrend } from '@/api/dashboard'
import { getReviews } from '@/api/reviews'
import { formatDateTime } from '@/utils/format'
import StatusTag from '@/components/common/StatusTag.vue'
import axios from 'axios'

use([CanvasRenderer, LineChart, PieChart, BarChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent])

const period = ref('all')
const trendDays = ref(14)
const statsData = ref(null)
const trendData = ref([])
const recentReviews = ref([])

const statCards = computed(() => {
  const o = statsData.value?.overview || {}
  const p = statsData.value?.period_stats || {}
  return [
    { key: 'projects', label: '项目总数', value: o.total_projects || 0, icon: 'FolderOpened', color: '#409EFF' },
    { key: 'reviews', label: '评审总数', value: p.review_count ?? o.total_reviews ?? 0, icon: 'Document', color: '#67C23A' },
    { key: 'completed', label: '已完成', value: p.completed ?? o.completed ?? 0, icon: 'CircleCheck', color: '#E6A23C' },
    { key: 'failed', label: '失败数', value: p.failed ?? o.failed ?? 0, icon: 'CircleClose', color: '#F56C6C' },
    { key: 'critical', label: '严重问题', value: p.critical_count || 0, icon: 'WarningFilled', color: '#E6A23C' },
    { key: 'comments', label: '评论总数', value: p.avg_comments_per_review ? `${p.avg_comments_per_review}/次` : '0', icon: 'ChatDotRound', color: '#909399' },
  ]
})

const topProjects = computed(() => statsData.value?.top_projects || [])
const maxReviewCount = computed(() => Math.max(...topProjects.value.map(p => p.review_count), 1))
function rankBarWidth(count) {
  return Math.round((count / maxReviewCount.value) * 100)
}

const severityOption = computed(() => {
  const dist = statsData.value?.severity_distribution || []
  const colorMap = { critical: '#F56C6C', warning: '#E6A23C', suggestion: '#409EFF', info: '#909399' }
  const labelMap = { critical: '严重', warning: '警告', suggestion: '建议', info: '信息' }
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, textStyle: { color: '#909399' } },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '45%'],
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      data: dist.map(d => ({
        name: labelMap[d.severity] || d.severity,
        value: d.count,
        itemStyle: { color: colorMap[d.severity] || '#ccc' },
      })),
    }],
  }
})

const trendOption = computed(() => {
  const dates = trendData.value.map(d => d.date.slice(5))
  const completed = trendData.value.map(d => d.completed)
  const failed = trendData.value.map(d => d.failed)
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['已完成', '失败'], bottom: 0, textStyle: { color: '#909399' } },
    grid: { left: 40, right: 20, top: 20, bottom: 40 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#e6e6e6' } },
      axisLabel: { color: '#909399' },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#f0f0f0' } },
      axisLabel: { color: '#909399' },
    },
    series: [
      {
        name: '已完成',
        type: 'line',
        data: completed,
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { width: 2, color: '#67C23A' },
        areaStyle: {
          color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(103,194,58,0.25)' }, { offset: 1, color: 'rgba(103,194,58,0.02)' }] },
        },
        itemStyle: { color: '#67C23A' },
      },
      {
        name: '失败',
        type: 'line',
        data: failed,
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { width: 2, color: '#F56C6C' },
        itemStyle: { color: '#F56C6C' },
      },
    ],
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

async function loadStats() {
  try {
    statsData.value = await getDashboardStats(period.value)
  } catch {
    statsData.value = null
  }
}

async function loadTrend() {
  try {
    const res = await getDashboardTrend(trendDays.value)
    trendData.value = res.data || []
  } catch {
    trendData.value = []
  }
}

async function loadRecent() {
  try {
    const res = await getReviews({ limit: 8 })
    recentReviews.value = Array.isArray(res) ? res : []
  } catch {
    recentReviews.value = []
  }
}

onMounted(() => {
  loadStats()
  loadTrend()
  loadRecent()
  checkHealth()
})
</script>

<style lang="scss" scoped>
.period-bar {
  margin-bottom: 16px;
}

.stat-cards .el-col {
  margin-bottom: 0;
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
  &:hover { transform: translateY(-2px); }
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

.rank-list {
  padding: 0 4px;
}

.rank-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
  &:last-child { border-bottom: none; }
}

.rank-index {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: #f0f0f0;
  color: #909399;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  &.rank-top { background: #409EFF; color: #fff; }
}

.rank-name {
  width: 120px;
  font-size: 14px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rank-bar-wrapper {
  flex: 1;
  height: 8px;
  background: #f5f5f5;
  border-radius: 4px;
  overflow: hidden;
}

.rank-bar {
  height: 100%;
  background: linear-gradient(90deg, #409EFF, #67C23A);
  border-radius: 4px;
  transition: width 0.3s;
}

.rank-count {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  min-width: 30px;
  text-align: right;
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
  &:hover { background: #fafafa; margin: 0 -12px; padding: 12px; border-radius: 4px; }
  &:last-child { border-bottom: none; }
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
