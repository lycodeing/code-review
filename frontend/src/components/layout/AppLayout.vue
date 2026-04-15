<template>
  <div class="app-layout">
    <Sidebar />
    <div class="main-area" :class="{ collapsed: appStore.sidebarCollapsed }">
      <Header />
      <TabsView />
      <div class="content-area">
        <router-view v-slot="{ Component }">
          <transition name="fade-transform" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </div>
  </div>
</template>

<script setup>
import { watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useTabsStore } from '@/stores/tabs'
import Sidebar from './Sidebar.vue'
import Header from './Header.vue'
import TabsView from './TabsView.vue'

const route = useRoute()
const appStore = useAppStore()
const tabsStore = useTabsStore()

// 路由变化时更新标签页
watch(
  () => route.path,
  () => {
    if (route.name && !route.meta?.hidden) {
      tabsStore.addTab(route)
    }
  },
  { immediate: true }
)
</script>

<style lang="scss" scoped>
.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  margin-left: $sidebar-width;
  transition: margin-left $transition-duration;

  &.collapsed {
    margin-left: $sidebar-collapsed-width;
  }
}

.content-area {
  flex: 1;
  overflow-y: auto;
  background: $content-bg;
  padding: 16px;
}
</style>
