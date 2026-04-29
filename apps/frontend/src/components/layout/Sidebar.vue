<template>
  <div class="sidebar" :class="{ collapsed: appStore.sidebarCollapsed }">
    <!-- Logo 区域 -->
    <div class="logo">
      <el-icon :size="24"><Monitor /></el-icon>
      <span v-show="!appStore.sidebarCollapsed" class="logo-text">Code Review</span>
    </div>

    <!-- 导航菜单 -->
    <el-scrollbar>
      <el-menu
        :default-active="route.path"
        :collapse="appStore.sidebarCollapsed"
        :collapse-transition="false"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
      >
        <el-menu-item index="/dashboard">
          <el-icon><Odometer /></el-icon>
          <template #title>仪表盘</template>
        </el-menu-item>

        <el-menu-item index="/projects">
          <el-icon><FolderOpened /></el-icon>
          <template #title>项目管理</template>
        </el-menu-item>

        <el-menu-item index="/reviews">
          <el-icon><Document /></el-icon>
          <template #title>评审记录</template>
        </el-menu-item>

        <el-menu-item index="/templates">
          <el-icon><Tickets /></el-icon>
          <template #title>Prompt 模板</template>
        </el-menu-item>

        <el-sub-menu index="config">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统配置</span>
          </template>
          <el-menu-item index="/platforms">
            <el-icon><Connection /></el-icon>
            <template #title>平台配置</template>
          </el-menu-item>
          <el-menu-item index="/notifications">
            <el-icon><Bell /></el-icon>
            <template #title>通知配置</template>
          </el-menu-item>
          <el-menu-item index="/notification-templates">
            <el-icon><ChatDotSquare /></el-icon>
            <template #title>通知模板</template>
          </el-menu-item>
          <el-menu-item index="/llm-configs">
            <el-icon><Cpu /></el-icon>
            <template #title>LLM 配置</template>
          </el-menu-item>
          <el-menu-item index="/review-rules">
            <el-icon><Filter /></el-icon>
            <template #title>评审规则</template>
          </el-menu-item>
        </el-sub-menu>

        <el-menu-item index="/request-history">
          <el-icon><List /></el-icon>
          <template #title>请求历史</template>
        </el-menu-item>
      </el-menu>
    </el-scrollbar>
  </div>
</template>

<script setup>
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { Cpu, ChatDotSquare, Filter, List } from '@element-plus/icons-vue'

const route = useRoute()
const appStore = useAppStore()
</script>

<style lang="scss" scoped>
.sidebar {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  width: $sidebar-width;
  background: $sidebar-bg;
  transition: width $transition-duration;
  overflow: hidden;
  z-index: 100;
  display: flex;
  flex-direction: column;

  &.collapsed {
    width: $sidebar-collapsed-width;
  }
}

.logo {
  height: $header-height;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  white-space: nowrap;
  overflow: hidden;
}

.logo-text {
  background: linear-gradient(135deg, #409eff, #67c23a);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

// 覆盖 Element Plus 菜单样式
:deep(.el-menu) {
  border-right: none;
}

:deep(.el-sub-menu .el-menu-item) {
  padding-left: 52px !important;
}
</style>
