<template>
  <div class="page">
    <PageHeader title="错误日志" :showBack="true" backPath="/admin/system" />

    <div class="page-body">
      <!-- Stats -->
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:10px">
        <div class="stat-card">
          <div class="stat-num">{{ stats.total }}</div><div class="stat-label">总错误</div>
        </div>
        <div class="stat-card" style="background:var(--danger-light)">
          <div class="stat-num" style="color:var(--danger)">{{ stats.unrepaired }}</div><div class="stat-label">未修复</div>
        </div>
        <div class="stat-card">
          <div class="stat-num">{{ stats.backend }}</div><div class="stat-label">后端</div>
        </div>
        <div class="stat-card">
          <div class="stat-num">{{ stats.frontend }}</div><div class="stat-label">前端</div>
        </div>
      </div>

      <!-- Filters -->
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px">
        <select class="filter-select" v-model="filterRepair" @change="loadLogs(1)">
          <option :value="null">全部状态</option>
          <option :value="false">🔴 未修复</option>
          <option :value="true">✅ 已修复</option>
        </select>
        <select class="filter-select" v-model="filterSource" @change="loadLogs(1)">
          <option value="">全部来源</option>
          <option value="backend">后端</option>
          <option value="frontend">前端</option>
        </select>
        <input class="filter-input" v-model="filterType" placeholder="错误类型..." @keyup.enter="loadLogs(1)" />
        <button class="btn btn-sm btn-outline" @click="loadLogs(1)">🔍 筛选</button>
        <button class="btn btn-sm btn-outline" @click="refreshStats">📊 刷新</button>
      </div>

      <LoadSpinner v-if="loading" text="加载日志..." />

      <!-- Log List -->
      <template v-else>
        <div v-if="!logs.length" class="card" style="text-align:center;color:var(--gray-400);padding:40px">
          🎉 没有匹配的错误日志
        </div>

        <div v-for="log in logs" :key="log.id" class="card log-card" :class="{ repaired: log.repair }">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">
            <div style="flex:1;min-width:0">
              <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
                <span class="tag" :class="log.repair ? 'tag-green' : 'tag-red'">{{ log.repair ? '✅ 已修复' : '🔴 未修复' }}</span>
                <span class="tag tag-gray">{{ log.source }}</span>
                <span class="tag tag-gray">{{ log.method }}</span>
                <span style="font-weight:600;font-size:13px;word-break:break-all">{{ log.endpoint }}</span>
              </div>
              <div style="margin-top:6px;font-size:13px;color:var(--gray-700);word-break:break-all">
                <span class="tag" style="background:var(--danger-light);color:var(--danger)">{{ log.error_type }}</span>
                {{ log.error_message }}
              </div>
              <div style="margin-top:4px;font-size:11px;color:var(--gray-400)">
                {{ formatTime(log.timestamp) }}
                <span v-if="log.user_name"> · {{ log.user_name }}</span>
                <span v-if="log.status_code"> · HTTP {{ log.status_code }}</span>
              </div>
            </div>
            <button v-if="!log.repair" class="btn btn-sm btn-primary" @click="markRepaired(log)" :disabled="repairing === log.id">
              {{ repairing === log.id ? '...' : '标记修复' }}
            </button>
          </div>

          <!-- Expandable details -->
          <details v-if="log.stack_trace || log.request_body || log.repair_note" style="margin-top:8px">
            <summary style="font-size:12px;color:var(--gray-500);cursor:pointer">查看详情</summary>
            <div v-if="log.stack_trace" style="margin-top:6px">
              <div style="font-size:11px;color:var(--gray-400);margin-bottom:2px">堆栈跟踪:</div>
              <pre style="background:var(--gray-50);padding:8px;border-radius:4px;font-size:11px;overflow-x:auto;max-height:150px">{{ log.stack_trace }}</pre>
            </div>
            <div v-if="log.request_body" style="margin-top:6px">
              <div style="font-size:11px;color:var(--gray-400);margin-bottom:2px">请求体:</div>
              <pre style="background:var(--gray-50);padding:8px;border-radius:4px;font-size:11px;overflow-x:auto;max-height:100px">{{ log.request_body }}</pre>
            </div>
            <div v-if="log.repair_note" style="margin-top:6px">
              <div style="font-size:11px;color:var(--gray-400)">修复说明: {{ log.repair_note }}</div>
              <div style="font-size:11px;color:var(--gray-400)">修复人: {{ log.repaired_by }} · {{ formatTime(log.repaired_at) }}</div>
            </div>
          </details>
        </div>

        <!-- Pagination -->
        <div v-if="totalPages > 1" style="display:flex;justify-content:center;gap:4px;margin-top:10px">
          <button class="btn btn-sm btn-outline" :disabled="page <= 1" @click="loadLogs(page - 1)">‹</button>
          <span style="padding:6px 10px;font-size:13px">{{ page }} / {{ totalPages }}</span>
          <button class="btn btn-sm btn-outline" :disabled="page >= totalPages" @click="loadLogs(page + 1)">›</button>
        </div>
      </template>
    </div>

    <BottomNav :items="navItems" active="system" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import PageHeader from '@/components/PageHeader.vue'
import BottomNav from '@/components/BottomNav.vue'
import LoadSpinner from '@/components/LoadSpinner.vue'
import { icons } from '@/utils/icons'
import axios from 'axios'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()

const loading = ref(true)
const logs = ref([])
const stats = ref({ total: 0, unrepaired: 0, backend: 0, frontend: 0 })
const page = ref(1)
const totalPages = ref(1)
const repairing = ref(null)

const filterRepair = ref(null)
const filterSource = ref('')
const filterType = ref('')

const navItems = [
  { key: 'dashboard', label: '总览', icon: icons.dashboard },
  { key: 'org', label: '组织', icon: icons.org },
  { key: 'system', label: '系统', icon: icons.settings },
  { key: 'diagnosis', label: '诊断', icon: icons.diagnosis },
  { key: 'me', label: '我的', icon: icons.home },
]

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

async function loadLogs(p) {
  loading.value = true
  page.value = p || 1
  try {
    const token = localStorage.getItem('token')
    const params = { page: page.value, page_size: 20 }
    if (filterRepair.value !== null) params.repair = filterRepair.value
    if (filterSource.value) params.source = filterSource.value
    if (filterType.value) params.error_type = filterType.value

    const res = await axios.get('/api/logs/', { params, headers: { Authorization: `Bearer ${token}` } })
    const data = res.data.data || res.data
    logs.value = data.items || []
    totalPages.value = data.pages || 1
  } catch {
    appStore.showToast('加载日志失败')
  } finally {
    loading.value = false
  }
}

async function refreshStats() {
  try {
    const token = localStorage.getItem('token')
    const res = await axios.get('/api/logs/stats', { headers: { Authorization: `Bearer ${token}` } })
    stats.value = res.data.data || res.data || { total: 0, unrepaired: 0, backend: 0, frontend: 0 }
  } catch {}
}

async function markRepaired(log) {
  if (!confirm(`标记此错误为已修复？\n${log.error_type}: ${log.error_message?.slice(0, 80)}`)) return
  repairing.value = log.id
  try {
    const token = localStorage.getItem('token')
    await axios.put(`/api/logs/${log.id}/repair`, { repair_note: 'Agent手动修复' }, { headers: { Authorization: `Bearer ${token}` } })
    log.repair = true
    log.repair_note = 'Agent手动修复'
    log.repaired_at = new Date().toISOString()
    log.repaired_by = '当前用户'
    appStore.showToast('已标记为修复')
    refreshStats()
  } catch {
    appStore.showToast('操作失败')
  } finally {
    repairing.value = null
  }
}

function onNav(key) {
  const map = {
    dashboard: '/admin/dashboard',
    org: '/admin/org',
    diagnosis: '/admin/diagnosis',
    system: '/admin/system',
    me: '/admin/me',
  }
  if (map[key]) router.push(map[key])
}

onMounted(() => {
  loadLogs(1)
  refreshStats()
})
</script>

<style scoped>
.stat-card {
  background: #fff;
  border-radius: 8px;
  padding: 10px 8px;
  text-align: center;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
}
.stat-num { font-size: 22px; font-weight: 700; }
.stat-label { font-size: 10px; color: var(--gray-400); margin-top: 2px; }
.filter-select, .filter-input {
  height: 34px;
  border: 1px solid var(--gray-200);
  border-radius: 6px;
  padding: 0 8px;
  font-size: 12px;
  background: #fff;
}
.filter-select { min-width: 90px; }
.filter-input { min-width: 120px; flex: 1; }
.log-card { margin-bottom: 8px; }
.log-card.repaired { opacity: 0.7; background: var(--gray-50); }
</style>
