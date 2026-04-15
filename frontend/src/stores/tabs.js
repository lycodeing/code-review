import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

export const useTabsStore = defineStore('tabs', () => {
  const router = useRouter()
  const activeTab = ref('/dashboard')
  const tabs = ref([
    { path: '/dashboard', title: '仪表盘', closable: false }
  ])

  /** 添加标签页 */
  function addTab(route) {
    if (!tabs.value.find((t) => t.path === route.path)) {
      tabs.value.push({
        path: route.path,
        title: route.meta?.title || route.name || route.path,
        closable: route.path !== '/dashboard'
      })
    }
    activeTab.value = route.path
  }

  /** 关闭标签页 */
  function closeTab(path) {
    const index = tabs.value.findIndex((t) => t.path === path)
    if (index === -1) return

    tabs.value.splice(index, 1)

    // 如果关闭的是当前激活的标签页，切换到相邻标签页
    if (activeTab.value === path) {
      const next = tabs.value[index] || tabs.value[index - 1]
      if (next) {
        activeTab.value = next.path
        router.push(next.path)
      }
    }
  }

  /** 关闭其他标签页 */
  function closeOtherTabs(path) {
    tabs.value = tabs.value.filter((t) => !t.closable || t.path === path)
    if (!tabs.value.find((t) => t.path === activeTab.value)) {
      activeTab.value = path
      router.push(path)
    }
  }

  /** 关闭所有可关闭的标签页 */
  function closeAllTabs() {
    tabs.value = tabs.value.filter((t) => !t.closable)
    activeTab.value = '/dashboard'
    router.push('/dashboard')
  }

  return { activeTab, tabs, addTab, closeTab, closeOtherTabs, closeAllTabs }
})
