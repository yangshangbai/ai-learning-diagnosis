<template>
  <div class="page">
    <PageHeader title="我的" />
    <div class="page-body">
      <!-- Avatar and Info Card -->
      <div class="card" style="text-align:center">
        <div :style="{ width:'60px',height:'60px',borderRadius:'50%',background:'var(--primary)',color:'#fff',display:'flex',alignItems:'center',justifyContent:'center',fontSize:'28px',fontWeight:'700',margin:'0 auto' }">
          {{ (user?.name || '?')[0] }}
        </div>
        <div style="font-size:18px;font-weight:700;margin-top:8px">{{ user?.name || '管理员' }}</div>
        <div style="font-size:12px;color:var(--gray-400);margin-top:4px">{{ user?.phone || '' }} · {{ roleText }}</div>
      </div>

      <!-- Quick Links -->
      <div class="card" style="margin-top:12px">
        <div class="card-header"><span class="card-title">快捷入口</span></div>
        <div v-if="quickLinks.length === 0" style="text-align:center;color:var(--gray-400);padding:20px">暂无快捷入口</div>
        <div v-for="entry in quickLinks" :key="entry.path"
          style="padding:12px 0;border-bottom:1px solid var(--gray-100);cursor:pointer;display:flex;align-items:center;gap:8px"
          @click="router.push(entry.path)">
          <span v-html="entry.icon" style="width:20px;height:20px;display:inline-flex;align-items:center"></span>
          <span style="flex:1">{{ entry.label }}</span>
          <span style="color:var(--gray-300)">→</span>
        </div>
      </div>

      <!-- Logout Button -->
      <button class="btn btn-danger btn-block" style="height:48px;font-size:16px;margin-top:20px" @click="logout">
        {{ '退出登录' }}
      </button>
    </div>

    <BottomNav :items="navItems" active="me" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import BottomNav from '@/components/BottomNav.vue'
import { useAuthStore } from '@/stores/auth'
import { icons } from '@/utils/icons'
import { roleLabel } from '@/utils/helpers'

const router = useRouter()
const authStore = useAuthStore()

const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

const role = computed(() => user.value?.role || '')

const roleText = computed(() => roleLabel(role.value))

const quickLinks = computed(() => {
  const links = []
  // 意见反馈 — 所有角色可见
  links.push({ path: '/feedback', label: '修改意见和BUG提交', icon: '💬' })
  if (['admin', 'super'].includes(role.value)) {
    links.push({ path: '/admin/dashboard', label: '数据总览', icon: icons.dashboard })
    links.push({ path: '/admin/org', label: '组织管理', icon: icons.org })
    links.push({ path: '/admin/tasks', label: '任务管理', icon: icons.tasks })
    links.push({ path: '/admin/diagnosis', label: '诊断看板', icon: icons.diagnosis })
  }
  if (['research', 'super'].includes(role.value)) {
    links.push({ path: '/admin/knowledge', label: '知识体系', icon: icons.knowledge })
    links.push({ path: '/admin/qbank', label: '题库管理', icon: icons.qbank })
    links.push({ path: '/admin/ai', label: 'AI助手', icon: icons.ai })
  }
  if (role.value === 'super') {
    links.push({ path: '/admin/system', label: '系统管理', icon: icons.settings })
    links.push({ path: '/admin/audit', label: '审计日志', icon: icons.log })
    links.push({ path: '/admin/remote', label: '远程协助', icon: icons.remote })
  }
  return links
})

const adminNav = [
  { key: 'dashboard', label: '总览', icon: icons.dashboard },
  { key: 'org', label: '组织', icon: icons.org },
  { key: 'tasks', label: '任务', icon: icons.tasks },
  { key: 'diagnosis', label: '诊断', icon: icons.diagnosis },
  { key: 'me', label: '我的', icon: icons.home },
]

const researchNav = [
  { key: 'knowledge', label: '知识库', icon: icons.knowledge },
  { key: 'qbank', label: '题库', icon: icons.qbank },
  { key: 'ai', label: 'AI', icon: icons.ai },
  { key: 'diagnosis', label: '诊断', icon: icons.diagnosis },
  { key: 'me', label: '我的', icon: icons.home },
]

const superNav = [
  { key: 'dashboard', label: '总览', icon: icons.dashboard },
  { key: 'org', label: '组织', icon: icons.org },
  { key: 'system', label: '系统', icon: icons.settings },
  { key: 'diagnosis', label: '诊断', icon: icons.diagnosis },
  { key: 'me', label: '我的', icon: icons.home },
]

const navItems = computed(() => {
  if (role.value === 'research') return researchNav
  if (role.value === 'super') return superNav
  return adminNav
})

function logout() {
  authStore.logout()
  router.push('/login')
}

function onNav(key) {
  const r = role.value
  if (r === 'admin' || r === 'super') {
    const map = {
      dashboard: '/admin/dashboard',
      org: '/admin/org',
      tasks: '/admin/tasks',
      diagnosis: '/admin/diagnosis',
      me: '/admin/me'
    }
    if (map[key]) router.push(map[key])
  } else {
    const map = {
      knowledge: '/admin/knowledge',
      qbank: '/admin/qbank',
      ai: '/admin/ai',
      diagnosis: '/admin/diagnosis',
      me: '/admin/me'
    }
    if (map[key]) router.push(map[key])
  }
}

onMounted(() => {
  const stored = localStorage.getItem('user')
  if (stored) {
    try { user.value = JSON.parse(stored) } catch (e) {}
  }
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.card-title {
  font-weight: 600;
  font-size: 14px;
}
</style>
