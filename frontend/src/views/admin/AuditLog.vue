<template>
  <div class="page">
    <PageHeader title="操作记录" :showBack="true" backPath="/admin/system" />
    <div class="page-body">
      <div style="font-size:11px;color:var(--gray-400);margin-bottom:8px">{{ '仅超级管理员可见' }}</div>

      <!-- Filter Bar -->
      <div class="filter-bar">
        <input
          class="input"
          v-model="filters.operator"
          placeholder="操作人搜索..."
          @input="onFilterChange"
        />
        <input
          type="date"
          class="input"
          v-model="filters.startDate"
          @change="onFilterChange"
        />
        <input
          type="date"
          class="input"
          v-model="filters.endDate"
          @change="onFilterChange"
        />
        <select class="input select" v-model="filters.actionType" @change="onFilterChange">
          <option value="">全部类型</option>
          <option value="upload">上传试卷</option>
          <option value="correct">批改完成</option>
          <option value="update">更新规则</option>
          <option value="view">查看</option>
          <option value="create">创建计划</option>
          <option value="sync">同步</option>
          <option value="ai">AI调用</option>
        </select>
      </div>

      <!-- Loading -->
      <LoadSpinner v-if="loading" text="加载操作记录..." />

      <!-- Error -->
      <div v-else-if="error" style="text-align:center;color:var(--danger);padding:32px 16px">
        <div style="margin-bottom:8px">{{ error }}</div>
        <button class="btn btn-sm btn-outline" @click="fetchLogs()">重试</button>
      </div>

      <!-- Empty -->
      <div v-else-if="logs.length === 0" style="text-align:center;color:var(--gray-400);padding:40px 20px">
        暂无操作记录
      </div>

      <!-- Timeline -->
      <div v-else class="timeline">
        <div v-for="l in logs" :key="l.id" class="timeline-item">
          <div class="timeline-time">{{ formatTime(l.time || l.created_at) }}</div>
          <div class="timeline-content">
            <b>{{ l.operator || l.op || l.user_name }}</b>
            {{ l.action || l.action_desc || l.detail }}
            <b v-if="l.target"> {{ l.target }}</b>
            <span v-if="l.ai || l.is_ai" class="tag tag-primary" style="margin-left:4px">AI调用</span>
          </div>
        </div>
      </div>

      <!-- Pagination -->
      <div v-if="hasMore && logs.length > 0" style="text-align:center;margin-top:12px">
        <button class="btn btn-outline btn-sm" @click="loadMore" :disabled="loadingMore">
          {{ loadingMore ? '加载中...' : '加载更多' }}
        </button>
      </div>
    </div>

    <BottomNav :items="navItems" active="system" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import BottomNav from '@/components/BottomNav.vue'
import LoadSpinner from '@/components/LoadSpinner.vue'
import { auditAPI } from '@/api/audit'
import { useAuthStore } from '@/stores/auth'
import { icons } from '@/utils/icons'

const router = useRouter()
const authStore = useAuthStore()

const user = computed(() => authStore.user || JSON.parse(localStorage.getItem('user') || 'null'))

const loading = ref(true)
const loadingMore = ref(false)
const error = ref('')
const logs = ref([])
const page = ref(1)
const hasMore = ref(false)
let debounceTimer = null

const filters = reactive({
  operator: '',
  startDate: '',
  endDate: '',
  actionType: ''
})

const navItems = [
  { key: 'dashboard', label: '总览', icon: icons.dashboard },
  { key: 'org', label: '组织', icon: icons.org },
  { key: 'system', label: '系统', icon: icons.settings },
  { key: 'diagnosis', label: '诊断', icon: icons.diagnosis },
  { key: 'me', label: '我的', icon: icons.home },
]

function formatTime(t) {
  if (!t) return ''
  const d = new Date(t)
  if (isNaN(d.getTime())) return t
  const now = new Date()
  const diff = now - d
  if (diff < 86400000) {
    return '今天 ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } else if (diff < 172800000) {
    return '昨天 ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } else if (diff < 259200000) {
    return '前天 ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('zh-CN') + ' ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function buildParams() {
  const params = { page: page.value, page_size: 20 }
  if (filters.operator) params.operator = filters.operator
  if (filters.startDate) params.start_date = filters.startDate
  if (filters.endDate) params.end_date = filters.endDate
  if (filters.actionType) params.action_type = filters.actionType
  return params
}

async function fetchLogs(append = false) {
  try {
    if (!append) {
      loading.value = true
      error.value = ''
    } else {
      loadingMore.value = true
    }
    const params = buildParams()
    const res = await auditAPI.getList(params)
    const items = res?.data || res?.items || res?.results || []
    const total = res?.total || res?.count || items.length

    if (append) {
      logs.value = [...logs.value, ...items]
    } else {
      logs.value = items
    }
    hasMore.value = logs.value.length < total
    page.value = append ? page.value + 1 : 1
  } catch (e) {
    if (!append) {
      error.value = e.response?.data?.detail || e.message || '加载失败，请重试'
    }
    console.warn('Failed to fetch audit logs:', e)
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function loadMore() {
  page.value++
  fetchLogs(true)
}

function onFilterChange() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    page.value = 1
    fetchLogs()
  }, 300)
}

function onNav(key) {
  const map = {
    dashboard: '/admin/dashboard',
    org: '/admin/org',
    diagnosis: '/admin/diagnosis',
    system: '/admin/system',
    me: '/admin/me'
  }
  if (map[key]) router.push(map[key])
}

onMounted(() => {
  fetchLogs()
})
</script>

<style scoped>
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 10px;
}
.filter-bar .input {
  height: 34px;
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-sm);
  padding: 0 8px;
  font-size: 12px;
  box-sizing: border-box;
}
.filter-bar .input[type="date"] {
  width: 120px;
}
.filter-bar .input[type="text"],
.filter-bar input:not([type]) {
  flex: 1;
  min-width: 100px;
}
.filter-bar .select {
  appearance: auto;
  min-width: 90px;
}
.timeline {
  padding-left: 8px;
}
.timeline-item {
  position: relative;
  padding-left: 20px;
  border-left: 2px solid var(--gray-200);
  padding-bottom: 16px;
}
.timeline-item::before {
  content: '';
  position: absolute;
  left: -5px;
  top: 4px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--primary);
}
.timeline-time {
  font-size: 11px;
  color: var(--gray-400);
  margin-bottom: 4px;
}
.timeline-content {
  font-size: 13px;
  color: var(--gray-700);
}
</style>
