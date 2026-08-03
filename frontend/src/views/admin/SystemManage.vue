<template>
  <div class="page">
    <PageHeader title="系统管理" />
    <div class="page-body">
      <div v-for="it in menuItems" :key="it.l" class="card"
        style="display:flex;align-items:center;gap:10px;cursor:pointer"
        @click="it.p ? router.push(it.p) : showToast(it.l)">
        <span style="font-size:22px">{{ it.icon }}</span>
        <div style="flex:1">
          <div style="font-weight:600;font-size:14px">{{ it.l }}</div>
          <div style="font-size:11px;color:var(--gray-400)">{{ it.d }}</div>
        </div>
        <span style="color:var(--gray-300)">→</span>
      </div>
    </div>

    <BottomNav :items="navItems" active="system" @nav="onNav" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import BottomNav from '@/components/BottomNav.vue'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { icons } from '@/utils/icons'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()

const user = computed(() => authStore.user || JSON.parse(localStorage.getItem('user') || 'null'))

const menuItems = [
  { icon: '📋', l: '操作记录', d: '查看所有关键操作日志', p: '/admin/audit' },
  { icon: '🔄', l: '远程协助', d: '代老师处理后台事务', p: '/admin/remote' },
  { icon: '🧠', l: 'AI模型配置', d: '设置AI服务商和API密钥', p: '/admin/ai-settings' },
  { icon: '🐛', l: '错误日志', d: '查看系统错误和异常记录', p: '/admin/logs' },
  { icon: '⚙️', l: '权限配置', d: '管理角色和权限(演示)', p: '/admin/permissions' }
]

const navItems = [
  { key: 'dashboard', label: '总览', icon: icons.dashboard },
  { key: 'org', label: '组织', icon: icons.org },
  { key: 'system', label: '系统', icon: icons.settings },
  { key: 'diagnosis', label: '诊断', icon: icons.diagnosis },
  { key: 'me', label: '我的', icon: icons.home },
]

function showToast(msg) {
  appStore.showToast(msg)
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
</script>
