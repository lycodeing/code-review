import { ref, reactive } from 'vue'

/**
 * 通用表格组合式函数
 * 封装分页、加载状态等通用逻辑
 */
export function useTable(fetchApi, defaultPageSize = 20) {
  const loading = ref(false)
  const tableData = ref([])
  const total = ref(0)

  const pagination = reactive({
    page: 1,
    pageSize: defaultPageSize
  })

  /** 加载数据 */
  async function loadData(params = {}) {
    loading.value = true
    try {
      const offset = (pagination.page - 1) * pagination.pageSize
      const res = await fetchApi({
        limit: pagination.pageSize,
        offset,
        ...params
      })
      // 兼容数组和分页对象两种响应格式
      if (Array.isArray(res)) {
        tableData.value = res
        total.value = res.length
      } else {
        tableData.value = res.items || res.data || []
        total.value = res.total || 0
      }
    } catch (e) {
      tableData.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  /** 页码变化 */
  function handlePageChange(page) {
    pagination.page = page
    loadData()
  }

  /** 每页条数变化 */
  function handleSizeChange(size) {
    pagination.pageSize = size
    pagination.page = 1
    loadData()
  }

  /** 重置分页 */
  function resetPagination() {
    pagination.page = 1
  }

  return {
    loading,
    tableData,
    total,
    pagination,
    loadData,
    handlePageChange,
    handleSizeChange,
    resetPagination
  }
}
