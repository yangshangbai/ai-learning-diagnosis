<template>
  <div class="login-page">
    <div class="login-card fade-in">
      <div style="text-align:center;margin-bottom:20px">
        <div style="font-size:48px">🧠</div>
        <h2 style="font-size:20px;margin-top:8px">AI学习诊断系统</h2>
        <p style="font-size:13px;color:var(--gray-400);margin-top:4px">面向培训机构的智能教学助手 v2.0</p>
      </div>
      <div class="input-group">
        <label style="font-size:13px;color:var(--gray-500)">手机号</label>
        <input
          class="input"
          v-model="phone"
          placeholder="输入手机号登录"
          style="height:48px;font-size:15px"
          @keyup.enter="handleLogin"
          list="account-list"
          autocomplete="off"
        />
        <datalist id="account-list">
          <option v-for="a in quickAccounts" :key="a.phone" :value="a.phone">{{ a.name }} · {{ a.roleLabel }}</option>
        </datalist>
        <div style="font-size:11px;color:var(--gray-400);margin-top:4px">
          演示账号：李老师 13800001111 | 王校长 13900001111 | 超级管理员 13900003333
        </div>
      </div>
      <div class="input-group">
        <label style="font-size:13px;color:var(--gray-500)">密码 <span style="font-size:11px;color:var(--gray-400)">（默认 demo123）</span></label>
        <input class="input" type="password" v-model="password" placeholder="请输入密码" style="height:48px;font-size:15px" @keyup.enter="handleLogin" />
      </div>
      <button class="btn btn-primary btn-block" style="height:48px;font-size:16px;margin-top:8px" @click="handleLogin" :disabled="!phone || loading">
        <span v-if="loading">登录中...</span>
        <span v-else>进入系统</span>
      </button>
      <p v-if="error" style="color:var(--danger);font-size:13px;text-align:center;margin-top:12px">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import axios from 'axios'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()

const phone = ref('')
const password = ref('demo123')
const loading = ref(false)
const error = ref('')

// Quick accounts list — fetched from public API + demo fallback
const quickAccounts = ref([
  { phone: '13800001111', name: '李老师', roleLabel: '老师' },
  { phone: '13900001111', name: '王校长', roleLabel: '管理员' },
  { phone: '13900003333', name: '超级管理员', roleLabel: '超级管理员' },
])

onMounted(async () => {
  try {
    const res = await axios.get('/api/auth/teachers')
    const data = res.data || res
    if (Array.isArray(data) && data.length > 0) {
      const roleMap = { teacher: '老师', admin: '管理员', research: '教研员', super: '超级管理员' }
      quickAccounts.value = data.map(u => ({
        phone: u.phone,
        name: u.name,
        roleLabel: roleMap[u.role] || u.role,
      }))
    }
  } catch {
    // Keep demo fallback
  }
})

async function handleLogin() {
  const phoneVal = phone.value.trim()
  if (!phoneVal || !password.value) {
    error.value = '请输入手机号和密码'
    return
  }
  if (!/^1[3-9]\d{9}$/.test(phoneVal)) {
    error.value = '请输入正确的手机号'
    return
  }

  loading.value = true
  error.value = ''
  try {
    const user = await authStore.login(phoneVal, password.value)
    if (user.role === 'teacher') {
      router.push('/teacher/students')
    } else if (user.role === 'admin') {
      router.push('/admin/dashboard')
    } else if (user.role === 'research') {
      router.push('/admin/knowledge')
    } else {
      router.push('/admin/dashboard')
    }
  } catch (e) {
    // If API fails, try mock login for demo accounts
    const demoAcc = quickAccounts.value.find(a => a.phone === phoneVal)
    if (demoAcc && password.value === 'demo123') {
      const demoUser = {
        id: demoAcc.phone, name: demoAcc.name, phone: demoAcc.phone,
        role: demoAcc.roleLabel === '老师' ? 'teacher' :
              demoAcc.roleLabel === '管理员' ? 'admin' :
              demoAcc.roleLabel === '教研员' ? 'research' : 'super',
        grades: [], subjects: [], classes: []
      }
      localStorage.setItem('token', 'demo-token')
      localStorage.setItem('user', JSON.stringify(demoUser))
      localStorage.setItem('role', demoUser.role)
      authStore.user = demoUser
      authStore.token = 'demo-token'
      if (demoUser.role === 'teacher') router.push('/teacher/students')
      else if (demoUser.role === 'admin') router.push('/admin/dashboard')
      else if (demoUser.role === 'research') router.push('/admin/knowledge')
      else router.push('/admin/dashboard')
      return
    }
    error.value = e?.response?.data?.detail || e?.message || '登录失败，请检查手机号和密码'
  } finally {
    loading.value = false
  }
}
</script>
