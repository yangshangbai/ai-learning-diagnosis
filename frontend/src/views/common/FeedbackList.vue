<template>
  <div class="page feedback-list-page">
    <PageHeader title="修改意见和BUG提交" showBack />

    <!-- filter bar -->
    <div class="filter-bar">
      <input v-model="searchText" class="search-input" placeholder="搜索..." @input="onSearch" />
      <select v-model="statusFilter" class="status-select" @change="loadList">
        <option value="">全部</option>
        <option value="已提交">已提交</option>
        <option value="已受理">已受理</option>
        <option value="已完成">已完成</option>
      </select>
      <button class="btn btn-primary btn-sm" @click="openCreate">+ 提交新反馈</button>
    </div>

    <LoadSpinner v-if="loading" />

    <!-- list -->
    <div v-else-if="items.length" class="feedback-items">
      <div v-for="fb in items" :key="fb.id" class="feedback-card" @click="openView(fb)">
        <div class="fb-meta">
          <span class="fb-user">{{ fb.username }}</span>
          <span class="fb-time">{{ formatTime(fb.submitted_at) }}</span>
        </div>
        <div class="fb-title">{{ fb.title }}</div>
        <div class="fb-footer">
          <span class="status-badge" :class="'status-' + fb.status">{{ fb.status }}</span>
          <div class="fb-actions" @click.stop>
            <button v-if="fb.status === '已提交' && canModify(fb)" class="btn btn-xs" @click="openEdit(fb)">编辑</button>
            <button v-if="fb.status === '已提交' && canModify(fb)" class="btn btn-xs btn-danger" @click="confirmDelete(fb)">删除</button>
            <button v-else class="btn btn-xs" @click="openView(fb)">查看</button>
          </div>
        </div>
      </div>
    </div>

    <EmptyState v-else text="暂无反馈" />

    <!-- pagination -->
    <div v-if="total > pageSize" class="pagination">
      <button :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
      <span>{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button :disabled="page >= Math.ceil(total / pageSize)" @click="goPage(page + 1)">下一页</button>
    </div>

    <!-- delete confirm modal -->
    <CrudModal v-if="deleteTarget" title="确认删除" @close="deleteTarget = null" @save="doDelete">
      <p>确定要删除「{{ deleteTarget.title }}」吗？此操作不可恢复。</p>
    </CrudModal>

    <BottomNav :items="navItems" active="" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { feedbackAPI } from '@/api/feedback'
import PageHeader from '@/components/PageHeader.vue'
import BottomNav from '@/components/BottomNav.vue'
import LoadSpinner from '@/components/LoadSpinner.vue'
import EmptyState from '@/components/EmptyState.vue'
import CrudModal from '@/components/CrudModal.vue'
import { icons } from '@/utils/icons'

const router = useRouter()
const auth = useAuthStore()

const navItems = computed(() => {
  const role = auth.user?.role
  if (role === 'teacher') return [
    { key: 'students', label: '学生', icon: icons.students },
    { key: 'tasks', label: '任务', icon: icons.tasks },
    { key: 'upload', label: '上传', icon: icons.upload },
    { key: 'exercise', label: '练习', icon: icons.exercise },
    { key: 'me', label: '我的', icon: icons.home },
  ]
  if (role === 'research') return [
    { key: 'knowledge', label: '知识库', icon: icons.knowledge },
    { key: 'qbank', label: '题库', icon: icons.qbank },
    { key: 'ai', label: 'AI', icon: icons.ai },
    { key: 'diagnosis', label: '诊断', icon: icons.diagnosis },
    { key: 'me', label: '我的', icon: icons.home },
  ]
  // admin / super
  return [
    { key: 'dashboard', label: '总览', icon: icons.dashboard },
    { key: 'org', label: '组织', icon: icons.org },
    { key: 'tasks', label: '任务', icon: icons.tasks },
    { key: 'diagnosis', label: '诊断', icon: icons.diagnosis },
    { key: 'me', label: '我的', icon: icons.home },
  ]
})

function onNav(key) {
  const role = auth.user?.role
  if (role === 'teacher') {
    if (key === 'students') router.push('/teacher/students')
    else if (key === 'tasks') router.push('/teacher/tasks')
    else if (key === 'upload') router.push('/teacher/upload')
    else if (key === 'exercise') router.push('/teacher/exercise')
    else if (key === 'me') router.push('/teacher/me')
  } else if (role === 'research') {
    if (key === 'knowledge') router.push('/admin/knowledge')
    else if (key === 'qbank') router.push('/admin/qbank')
    else if (key === 'ai') router.push('/admin/ai')
    else if (key === 'diagnosis') router.push('/admin/diagnosis')
    else if (key === 'me') router.push('/admin/me')
  } else {
    if (key === 'dashboard') router.push('/admin/dashboard')
    else if (key === 'org') router.push('/admin/org')
    else if (key === 'tasks') router.push('/admin/tasks')
    else if (key === 'diagnosis') router.push('/admin/diagnosis')
    else if (key === 'me') router.push('/admin/me')
  }
}

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const searchText = ref('')
const statusFilter = ref('')
const deleteTarget = ref(null)
let searchTimer = null

function canModify(fb) {
  return fb.user_id === auth.user?.id || auth.user?.role === 'admin' || auth.user?.role === 'super'
}

function formatTime(t) {
  if (!t) return '-'
  const d = new Date(t)
  return `${d.getMonth() + 1}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

async function loadList() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (statusFilter.value) params.status = statusFilter.value
    if (searchText.value) params.search = searchText.value
    const res = await feedbackAPI.list(params)
    const data = res?.items || res?.data || res || {}
    items.value = data?.items || data || []
    total.value = data?.total || items.value.length
  } catch { items.value = [] }
  finally { loading.value = false }
}

function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { page.value = 1; loadList() }, 300)
}

function goPage(p) { page.value = p; loadList() }

function openCreate() { router.push('/feedback/create') }
function openEdit(fb) { router.push(`/feedback/${fb.id}/edit`) }
function openView(fb) { router.push(`/feedback/${fb.id}`) }

function confirmDelete(fb) { deleteTarget.value = fb }

async function doDelete() {
  try {
    await feedbackAPI.delete(deleteTarget.value.id)
    deleteTarget.value = null
    loadList()
  } catch { alert('删除失败') }
}

onMounted(loadList)
</script>

<style scoped>
.feedback-list-page { padding: 16px; max-width: 800px; margin: 0 auto; }
.filter-bar { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.search-input { flex: 1; min-width: 120px; padding: 6px 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
.status-select { padding: 6px 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
.btn-xs { padding: 3px 10px; font-size: 12px; }
.btn-danger { background: #e74c3c; color: #fff; border: none; }
.feedback-card { background: #fff; border-radius: 10px; padding: 14px; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,.08); cursor: pointer; }
.fb-meta { display: flex; justify-content: space-between; font-size: 12px; color: #999; margin-bottom: 6px; }
.fb-title { font-size: 15px; font-weight: 600; margin-bottom: 8px; }
.fb-footer { display: flex; justify-content: space-between; align-items: center; }
.status-badge { font-size: 12px; padding: 2px 8px; border-radius: 4px; }
.status-已提交 { background: #fff3cd; color: #856404; }
.status-已受理 { background: #cce5ff; color: #004085; }
.status-已完成 { background: #d4edda; color: #155724; }
.fb-actions { display: flex; gap: 6px; }
.pagination { display: flex; justify-content: center; gap: 12px; align-items: center; margin-top: 16px; }
</style>
