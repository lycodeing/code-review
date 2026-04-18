<template>
  <div class="header">
    <!-- 左侧：折叠按钮 + 面包屑 -->
    <div class="header-left">
      <el-icon
        class="collapse-btn"
        @click="appStore.toggleSidebar"
      >
        <Fold v-if="!appStore.sidebarCollapsed" />
        <Expand v-else />
      </el-icon>

      <el-breadcrumb separator="/">
        <el-breadcrumb-item v-for="item in breadcrumbs" :key="item.path">
          {{ item.title }}
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <!-- 右侧：功能按钮 + 用户信息 -->
    <div class="header-right">
      <el-tooltip content="全屏" placement="bottom">
        <el-icon class="header-icon" @click="toggleFullscreen">
          <FullScreen />
        </el-icon>
      </el-tooltip>

      <el-dropdown @command="handleCommand">
        <div class="user-info">
          <el-avatar :size="32" class="user-avatar">
            {{ userStore.getUsername()?.charAt(0) || 'A' }}
          </el-avatar>
          <span class="user-name">{{ userStore.getUsername() || '管理员' }}</span>
          <el-icon><ArrowDown /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="logout">
              <el-icon><SwitchButton /></el-icon>
              退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import { ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const userStore = useUserStore()

// 面包屑
const breadcrumbs = computed(() => {
  const matched = route.matched.filter((item) => item.meta?.title)
  return [{ path: '/dashboard', title: '首页' }, ...matched.map((r) => ({
    path: r.path,
    title: r.meta.title
  }))]
})

// 全屏切换
function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen()
  } else {
    document.exitFullscreen()
  }
}

// 下拉菜单操作
function handleCommand(command) {
  if (command === 'logout') {
    ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }).then(() => {
      userStore.logout()
      router.push('/login')
    }).catch(() => {})
  }
}
</script>

<style lang="scss" scoped>
.header {
  height: $header-height;
  background: $header-bg;
  border-bottom: 1px solid $header-border;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.collapse-btn {
  font-size: 20px;
  cursor: pointer;
  color: #606266;
  transition: color 0.2s;

  &:hover {
    color: $primary-color;
  }
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-icon {
  font-size: 18px;
  cursor: pointer;
  color: #606266;
  transition: color 0.2s;

  &:hover {
    color: $primary-color;
  }
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: $border-radius;
  transition: background 0.2s;

  &:hover {
    background: #f5f7fa;
  }
}

.user-avatar {
  background: linear-gradient(135deg, #409eff, #67c23a);
  color: #fff;
  font-size: 14px;
}

.user-name {
  font-size: 14px;
  color: #303133;
}
</style>
