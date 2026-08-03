import { ref } from 'vue'
import { useAppStore } from '@/stores/app'

/**
 * Shared composable for common CRUD patterns.
 *
 * @param {Object} apiModule - API module with getList, create, update, remove methods
 * @param {Object} options - Optional config
 * @param {string} options.createMsg - Success toast for create
 * @param {string} options.updateMsg - Success toast for update
 * @param {string} options.deleteMsg - Success toast for delete
 * @param {string} options.deleteConfirm - Confirm message for delete
 * @param {Function} options.fetchFn - Custom fetch function (overrides default getList)
 */
export function useCrud(apiModule, options = {}) {
  const items = ref([])
  const loading = ref(false)
  const error = ref(null)
  const showModal = ref(false)
  const editingItem = ref(null)

  async function fetchList(params = {}) {
    loading.value = true
    error.value = null
    try {
      const fetchFn = options.fetchFn || apiModule.getList
      const res = await fetchFn(params)
      items.value = res.data?.items || res.items || res.data || []
    } catch (e) {
      error.value = e.response?.data?.detail || e.message || '加载失败'
      useAppStore().showToast('加载失败: ' + error.value)
    } finally {
      loading.value = false
    }
  }

  async function createItem(data) {
    try {
      await apiModule.create(data)
      useAppStore().showToast(options.createMsg || '创建成功')
      await fetchList()
      return true
    } catch (e) {
      useAppStore().showToast('创建失败: ' + (e.response?.data?.detail || e.message))
      return false
    }
  }

  async function updateItem(id, data) {
    try {
      await apiModule.update(id, data)
      useAppStore().showToast(options.updateMsg || '更新成功')
      await fetchList()
      return true
    } catch (e) {
      useAppStore().showToast('更新失败: ' + (e.response?.data?.detail || e.message))
      return false
    }
  }

  async function deleteItem(id) {
    if (!confirm(options.deleteConfirm || '确定要删除吗？')) return false
    try {
      await apiModule.remove(id)
      useAppStore().showToast(options.deleteMsg || '删除成功')
      await fetchList()
      return true
    } catch (e) {
      useAppStore().showToast('删除失败: ' + (e.response?.data?.detail || e.message))
      return false
    }
  }

  function openCreateModal() {
    editingItem.value = null
    showModal.value = true
  }

  function openEditModal(item) {
    editingItem.value = { ...item }
    showModal.value = true
  }

  function closeModal() {
    showModal.value = false
    editingItem.value = null
  }

  return {
    items,
    loading,
    error,
    showModal,
    editingItem,
    fetchList,
    createItem,
    updateItem,
    deleteItem,
    openCreateModal,
    openEditModal,
    closeModal
  }
}
