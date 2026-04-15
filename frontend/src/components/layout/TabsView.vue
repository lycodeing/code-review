<template>
  <div class="tabs-view" v-if="tabsStore.tabs.length > 1">
    <el-scrollbar>
      <div class="tabs-container">
        <div
          v-for="tab in tabsStore.tabs"
          :key="tab.path"
          class="tab-item"
          :class="{ active: tabsStore.activeTab === tab.path }"
          @click="switchTab(tab)"
          @contextmenu.prevent="showContextMenu($event, tab)"
        >
          <span class="tab-title">{{ tab.title }}</span>
          <el-icon
            v-if="tab.closable"
            class="tab-close"
            @click.stop="tabsStore.closeTab(tab.path)"
          >
            <Close />
          </el-icon>
        </div>
      </div>
    </el-scrollbar>

    <!-- 右键菜单 -->
    <div
      v-show="contextMenuVisible"
      class="context-menu"
      :style="{ left: contextMenuLeft + 'px', top: contextMenuTop + 'px' }"
    >
      <div class="menu-item" @click="closeOther">关闭其他</div>
      <div class="menu-item" @click="closeAll">关闭所有</div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useTabsStore } from '@/stores/tabs'

const router = useRouter()
const tabsStore = useTabsStore()

const contextMenuVisible = ref(false)
const contextMenuLeft = ref(0)
const contextMenuTop = ref(0)
const currentTab = ref(null)

function switchTab(tab) {
  tabsStore.activeTab = tab.path
  router.push(tab.path)
}

function showContextMenu(e, tab) {
  currentTab.value = tab
  contextMenuLeft.value = e.clientX
  contextMenuTop.value = e.clientY
  contextMenuVisible.value = true
  document.addEventListener('click', hideContextMenu)
}

function hideContextMenu() {
  contextMenuVisible.value = false
  document.removeEventListener('click', hideContextMenu)
}

function closeOther() {
  if (currentTab.value) {
    tabsStore.closeOtherTabs(currentTab.value.path)
  }
  hideContextMenu()
}

function closeAll() {
  tabsStore.closeAllTabs()
  hideContextMenu()
}
</script>

<style lang="scss" scoped>
.tabs-view {
  background: $header-bg;
  border-bottom: 1px solid $header-border;
  padding: 6px 16px;
  position: relative;
}

.tabs-container {
  display: flex;
  gap: 6px;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  font-size: 13px;
  color: #606266;
  background: #f5f7fa;
  border-radius: 3px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;

  &:hover {
    color: $primary-color;
  }

  &.active {
    background: $primary-color;
    color: #fff;

    .tab-close:hover {
      background: rgba(255, 255, 255, 0.3);
    }
  }
}

.tab-close {
  font-size: 12px;
  border-radius: 50%;
  padding: 2px;
  transition: background 0.2s;

  &:hover {
    background: rgba(0, 0, 0, 0.1);
  }
}

.context-menu {
  position: fixed;
  background: #fff;
  border-radius: $border-radius;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  padding: 4px 0;
  z-index: 3000;
}

.menu-item {
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
  color: #303133;

  &:hover {
    background: #f5f7fa;
    color: $primary-color;
  }
}
</style>
