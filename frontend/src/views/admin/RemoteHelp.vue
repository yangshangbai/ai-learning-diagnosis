<template>
  <div class="page">
    <PageHeader title="远程协助" :showBack="true" backPath="/admin/system" />
    <div class="page-body">
      <!-- Teacher Selector -->
      <div class="card" style="background:var(--primary-light);border-color:var(--primary)">
        <div style="font-size:12px;font-weight:600">{{ '选择协助老师' }}</div>
        <select
          class="input select"
          v-model="selectedTeacher"
          style="margin-top:6px;width:100%"
          :disabled="loadingTeachers"
        >
          <option value="">{{ loadingTeachers ? '加载中...' : '请选择老师' }}</option>
          <option v-for="t in teacherList" :value="t.id" :key="t.id">
            {{ t.name }} {{ t.subject ? '(' + t.subject + ')' : '' }}{{ t.grade ? ' - ' + t.grade : '' }}
          </option>
        </select>
      </div>

      <!-- Executable Operations -->
      <div class="card">
        <div style="font-weight:600;font-size:14px;margin-bottom:6px">可执行操作</div>
        <div
          v-for="op in operations"
          :key="op"
          style="padding:8px 0;border-bottom:1px solid var(--gray-50);display:flex;justify-content:space-between;align-items:center"
        >
          <span style="font-size:13px">{{ op }}</span>
          <button
            class="btn btn-sm btn-outline"
            @click="executeOp(op)"
            :disabled="executing || !selectedTeacher"
          >{{ executing === op ? '执行中...' : '执行' }}</button>
        </div>
        <!-- Result message -->
        <div v-if="opResult" style="margin-top:8px;font-size:12px;color:var(--gray-600);background:var(--gray-50);padding:6px 8px;border-radius:4px">
          {{ opResult }}
        </div>
      </div>

      <!-- Recent Assistance Records -->
      <div class="card">
        <div style="font-weight:600;font-size:14px;margin-bottom:6px">{{ '最近协助' }}</div>
        <LoadSpinner v-if="loadingHistory" text="加载记录..." />
        <div v-else-if="recentRecords.length === 0" style="text-align:center;color:var(--gray-400);padding:20px 0">暂无协助记录</div>
        <div
          v-for="r in recentRecords"
          :key="r.id"
          style="font-size:12px;padding:4px 0;border-bottom:1px solid var(--gray-50)"
        >
          <span style="color:var(--gray-400)">{{ formatTime(r.time || r.created_at) }}</span>
          {{ r.operator || r.op || '' }} {{ r.action || r.action_desc || r.detail || '' }}
        </div>
      </div>
    </div>

    <BottomNav :items="navItems" active="system" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import BottomNav from '@/components/BottomNav.vue'
import LoadSpinner from '@/components/LoadSpinner.vue'
import { teachersAPI } from '@/api/teachers'
import { remoteHelpAPI } from '@/api/remoteHelp'
import { useAuthStore } from '@/stores/auth'
import { icons } from '@/utils/icons'

const router = useRouter()
const authStore = useAuthStore()

const user = computed(() => authStore.user || JSON.parse(localStorage.getItem('user') || 'null'))

const selectedTeacher = ref('')
const loadingTeachers = ref(false)
const loadingHistory = ref(false)
const executing = ref(false)
const opResult = ref('')

const teacherList = ref([])

const operations = [
  '代创建任务',
  '代匹配上传',
  '代重跑AI',
  '代生成报告',
  '修改学生归属',
  '调整确认结果'
]

const recentRecords = ref([])

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

async function fetchTeachers() {
  loadingTeachers.value = true
  try {
    const res = await teachersAPI.getList()
    teacherList.value = res?.data || res?.items || res?.results || res || []
  } catch (e) {
    console.warn('Failed to fetch teachers:', e)
  } finally {
    loadingTeachers.value = false
  }
}

async function fetchHistory() {
  loadingHistory.value = true
  try {
    const res = await remoteHelpAPI.getHistory()
    recentRecords.value = res?.data || res?.items || res?.results || res || []
  } catch (e) {
    console.warn('Failed to fetch remote help history:', e)
    // Keep empty state on failure
  } finally {
    loadingHistory.value = false
  }
}

async function executeOp(op) {
  if (!selectedTeacher.value || executing.value) return
  executing.value = op
  opResult.value = ''
  try {
    const teacher = teacherList.value.find(t => t.id === selectedTeacher.value || t.id === Number(selectedTeacher.value))
    const teacherName = teacher?.name || '所选老师'
    const res = await remoteHelpAPI.execute({
      teacher_id: selectedTeacher.value,
      action: op,
      detail: `超级管理员代${teacherName}${op}`
    })
    const msg = res?.data?.message || res?.message || `已为${teacherName}执行"${op}"，已留痕`
    opResult.value = msg
    // Refresh history after successful operation
    fetchHistory()
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '操作执行失败'
    opResult.value = `错误: ${msg}`
    console.warn('Failed to execute remote help operation:', e)
  } finally {
    executing.value = false
  }
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
  fetchTeachers()
  fetchHistory()
})
</script>

<style scoped>
.input {
  width: 100%;
  height: 40px;
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-sm);
  padding: 0 12px;
  font-size: 14px;
  box-sizing: border-box;
}
.select {
  appearance: auto;
}
</style>
