<template>
  <div class="page">
    <PageHeader title="我的" />

    <div class="page-body">
      <!-- User Info Card -->
      <div class="card" style="text-align:center">
        <div
          :style="{
            width:'60px',height:'60px',borderRadius:'50%',
            background:'var(--primary)',color:'#fff',
            display:'flex',alignItems:'center',justifyContent:'center',
            fontSize:'28px',fontWeight:'700',margin:'0 auto'
          }"
        >{{ (user?.name || '?')[0] }}</div>
        <div style="font-size:18px;font-weight:700;margin-top:8px">{{ user?.name }}</div>
        <div style="font-size:12px;color:var(--gray-400)">{{ user?.phone }} · {{ roleLabel(user?.role) }}</div>
        <div v-if="user?.grades?.length || user?.subjects?.length" style="font-size:12px;color:var(--gray-500);margin-top:4px">
          {{ (user?.grades || []).join('/') }} · {{ (user?.subjects || []).join('/') }}
        </div>
      </div>

      <!-- Stats Card -->
      <div class="card">
        <div style="font-size:14px;padding:6px 0">&#x1F4CA; 管理班级：{{ classesCount }}个</div>
        <div style="font-size:14px;padding:6px 0">&#x1F465; 学生人数：{{ studentsCount }}人</div>
        <div style="font-size:14px;padding:6px 0">&#x1F4DD; 任务总数：{{ tasksCount }}个</div>
      </div>

      <!-- Logout Button -->
      <button class="btn btn-danger btn-block" style="height:48px;font-size:16px;margin-top:12px" @click="handleLogout">&#x1F6AA; 退出登录</button>
    </div>

    <BottomNav :items="teacherNav" active="me" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { studentsAPI } from '@/api/students'
import { tasksAPI } from '@/api/tasks'
import { classesAPI } from '@/api/classes'
import BottomNav from '@/components/BottomNav.vue'
import PageHeader from '@/components/PageHeader.vue'
import LoadSpinner from '@/components/LoadSpinner.vue'
import { icons } from '@/utils/icons'
import { roleLabel } from '@/utils/helpers'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()

const classesCount = ref(0)
const studentsCount = ref(0)
const tasksCount = ref(0)

const user = computed(() => authStore.user)

const teacherNav = [
  { key: 'students', label: '学生', icon: icons.students },
  { key: 'tasks', label: '任务', icon: icons.tasks },
  { key: 'upload', label: '上传', icon: icons.upload },
  { key: 'exercise', label: '练习', icon: icons.exercise },
  { key: 'me', label: '我的', icon: icons.home },
]

function onNav(key) {
  if (key === 'students') router.push('/teacher/students')
  else if (key === 'tasks') router.push('/teacher/tasks')
  else if (key === 'upload') router.push('/teacher/upload')
  else if (key === 'exercise') router.push('/teacher/exercise')
}

async function loadStats() {
  const userClasses = user.value?.classes || []
  try {
    const [classRes, stuRes, taskRes] = await Promise.allSettled([
      classesAPI.getList(),
      studentsAPI.getList(),
      tasksAPI.getList(),
    ])
    if (classRes.status === 'fulfilled') {
      const classes = classRes.value.data || classRes.value || []
      classesCount.value = userClasses.length || classes.filter(c => userClasses.includes(c.id)).length
    }
    if (stuRes.status === 'fulfilled') {
      const students = stuRes.value.data || stuRes.value || []
      studentsCount.value = students.filter(s => userClasses.includes(s.classId || s.class_id)).length
    }
    if (taskRes.status === 'fulfilled') {
      const tasks = taskRes.value.data || taskRes.value || []
      tasksCount.value = tasks.filter(t => userClasses.some(c => (t.classIds || t.class_ids || []).includes(c))).length
    }
  } catch {
    // Use defaults from user
    classesCount.value = userClasses.length
    studentsCount.value = 18 // demo default
    tasksCount.value = 5   // demo default
  }
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}

onMounted(loadStats)
</script>
