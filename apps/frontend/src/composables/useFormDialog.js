import { ref } from 'vue'

/**
 * 通用表单弹窗组合式函数
 * 封装 visible + currentItem 的 open/close/saved 逻辑
 */
export function useFormDialog() {
  const visible = ref(false)
  const currentItem = ref(null)

  function openForm(item = null) {
    currentItem.value = item
    visible.value = true
  }

  function closeForm() {
    visible.value = false
  }

  function onSaved(reloadFn) {
    visible.value = false
    if (typeof reloadFn === 'function') {
      reloadFn()
    }
  }

  return {
    visible,
    currentItem,
    openForm,
    closeForm,
    onSaved
  }
}
