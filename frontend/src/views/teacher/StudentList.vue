<template>
  <div class="page">
    <PageHeader :title="'我的学生 (' + students.length + ')'">
      <span style="font-size:13px;color:var(--gray-400)">{{ user?.name }}</span>
    </PageHeader>

    <div class="page-body">
      <LoadSpinner v-if="loading" text="加载学生数据..." />

      <template v-else>
        <div style="display:flex;gap:8px;margin-bottom:12px;overflow-x:auto;flex-wrap:wrap">
          <button
            v-for="c in myClasses"
            :key="c.id"
            class="btn btn-sm"
            :class="filterClass === c.id ? 'btn-primary' : 'btn-outline'"
            @click="filterClass = c.id"
          >{{ c.name }}</button>
          <button
            class="btn btn-sm"
            :class="filterClass === 'all' ? 'btn-primary' : 'btn-outline'"
            @click="filterClass = 'all'"
          >全部</button>
        </div>

        <div v-for="s in filteredStudents" :key="s.id" class="student-card" @click="goProfile(s.id)">
          <div
            :style="{
              width:'44px',height:'44px',borderRadius:'50%',
              background: (s.mastery >= 80) ? '#10B981' : (s.mastery >= 60) ? '#F59E0B' : '#EF4444',
              color:'#fff',display:'flex',alignItems:'center',justifyContent:'center',
              fontWeight:'700',fontSize:'18px',flexShrink:0
            }"
          >{{ (s.name || '?')[0] }}</div>
          <div style="flex:1;min-width:0">
            <div style="font-weight:600;font-size:15px">{{ s.name }}</div>
            <div style="font-size:11px;color:var(--gray-400)">{{ s.class_name || s.className }} · {{ s.grade }}</div>
            <div v-if="(s.weak || []).length" style="margin-top:3px">
              <span v-for="w in s.weak" :key="w" class="tag tag-red" style="margin-right:3px;font-size:10px">{{ w }}</span>
            </div>
          </div>
          <div style="text-align:right;flex-shrink:0">
            <div
              style="font-size:22px;font-weight:700"
              :style="{color: s.mastery >= 80 ? 'var(--success)' : s.mastery >= 60 ? 'var(--warning)' : 'var(--danger)'}"
            >{{ s.mastery }}%</div>
            <div
              style="font-size:11px"
              :style="{color: s.trend === 'up' ? 'var(--success)' : s.trend === 'down' ? 'var(--danger)' : 'var(--gray-400)'}"
            >{{ s.trend === 'up' ? '📈 +' : s.trend === 'down' ? '📉 ' : '' }}{{ s.trend !== 'stable' ? '' : s.trend }}</div>
          </div>
        </div>

        <EmptyState
          v-if="!loading && filteredStudents.length === 0"
          icon="👥" title="暂无学生数据"
          desc="请检查班级筛选或联系管理员添加学生"
        />
      </template>
    </div>

    <BottomNav :items="teacherNav" active="students" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { studentsAPI } from '@/api/students'
import { classesAPI } from '@/api/classes'
import BottomNav from '@/components/BottomNav.vue'
import PageHeader from '@/components/PageHeader.vue'
import LoadSpinner from '@/components/LoadSpinner.vue'
import EmptyState from '@/components/EmptyState.vue'
import { icons } from '@/utils/icons'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()

const loading = ref(true)
const students = ref([])
const allClasses = ref([])
const filterClass = ref('all')

const user = computed(() => authStore.user)

const teacherNav = [
  { key: 'students', label: '学生', icon: icons.students },
  { key: 'tasks', label: '任务', icon: icons.tasks },
  { key: 'upload', label: '上传', icon: icons.upload },
  { key: 'exercise', label: '练习', icon: icons.exercise },
  { key: 'me', label: '我的', icon: icons.home },
]

const myClasses = computed(() => {
  if (!user.value?.classes) return allClasses.value
  return allClasses.value.filter(c => user.value.classes.includes(c.id))
})

const filteredStudents = computed(() => {
  if (filterClass.value === 'all') return students.value
  return students.value.filter(s => s.class_id === filterClass.value || s.classId === filterClass.value)
})

async function loadData() {
  loading.value = true
  try {
    const [studentRes, classRes] = await Promise.allSettled([
      studentsAPI.getList(),
      classesAPI.getList()
    ])
    if (studentRes.status === 'fulfilled') {
      const raw = studentRes.value
      students.value = raw?.items || raw?.data || raw || []
    } else {
      loadMockStudents()
    }
    if (classRes.status === 'fulfilled') {
      const raw = classRes.value
      allClasses.value = raw?.items || raw?.data || raw || []
    } else {
      loadMockClasses()
    }
  } catch (e) {
    // Fallback: use mock data if API unavailable
    loadMockClasses()
    loadMockStudents()
  } finally {
    loading.value = false
  }
}

function loadMockClasses() {
  allClasses.value = [
    { id: 1, name: '五(1)班', grade: '五年级', subjects: ['数学'] },
    { id: 2, name: '五(2)班', grade: '五年级', subjects: ['数学'] },
    { id: 3, name: '六(1)班', grade: '六年级', subjects: ['数学'] },
    { id: 4, name: '六(2)班', grade: '六年级', subjects: ['数学'] },
    { id: 5, name: '初一(1)班', grade: '初一', subjects: ['数学'] },
    { id: 6, name: '初一(2)班', grade: '初一', subjects: ['数学'] },
    { id: 7, name: '初二(1)班', grade: '初二', subjects: ['数学', '物理'] },
    { id: 8, name: '初二(2)班', grade: '初二', subjects: ['数学', '物理'] },
    { id: 9, name: '初三(1)班', grade: '初三', subjects: ['数学', '物理', '化学'] },
    { id: 10, name: '初三(2)班', grade: '初三', subjects: ['数学', '物理', '化学'] },
  ]
}

function loadMockStudents() {
  students.value = [
    { id: 1, name: '张三', class_id: 1, classId: 1, class_name: '五(1)班', grade: '五年级', mastery: 85, trend: 'up', weak: ['分数通分'] },
    { id: 2, name: '李四', class_id: 1, classId: 1, class_name: '五(1)班', grade: '五年级', mastery: 72, trend: 'stable', weak: ['三角形面积'] },
    { id: 3, name: '王五', class_id: 1, classId: 1, class_name: '五(1)班', grade: '五年级', mastery: 58, trend: 'down', weak: ['异分母分数加减', '分数应用题'] },
    { id: 4, name: '赵六', class_id: 2, classId: 2, class_name: '五(2)班', grade: '五年级', mastery: 91, trend: 'up', weak: [] },
    { id: 5, name: '钱七', class_id: 2, classId: 2, class_name: '五(2)班', grade: '五年级', mastery: 67, trend: 'down', weak: ['长方体体积'] },
    { id: 6, name: '孙八', class_id: 3, classId: 3, class_name: '六(1)班', grade: '六年级', mastery: 78, trend: 'up', weak: ['百分数应用'] },
    { id: 7, name: '周九', class_id: 3, classId: 3, class_name: '六(1)班', grade: '六年级', mastery: 63, trend: 'down', weak: ['分数乘除', '比例'] },
    { id: 8, name: '吴十', class_id: 4, classId: 4, class_name: '六(2)班', grade: '六年级', mastery: 82, trend: 'up', weak: [] },
    { id: 9, name: '郑一', class_id: 5, classId: 5, class_name: '初一(1)班', grade: '初一', mastery: 75, trend: 'stable', weak: ['一元一次方程'] },
    { id: 10, name: '冯二', class_id: 5, classId: 5, class_name: '初一(1)班', grade: '初一', mastery: 68, trend: 'down', weak: ['有理数运算'] },
    { id: 11, name: '陈三', class_id: 6, classId: 6, class_name: '初一(2)班', grade: '初一', mastery: 88, trend: 'up', weak: [] },
    { id: 12, name: '褚四', class_id: 7, classId: 7, class_name: '初二(1)班', grade: '初二', mastery: 71, trend: 'stable', weak: ['一次函数', '浮力'] },
    { id: 13, name: '卫五', class_id: 7, classId: 7, class_name: '初二(1)班', grade: '初二', mastery: 55, trend: 'down', weak: ['三角形全等', '压强'] },
    { id: 14, name: '蒋六', class_id: 8, classId: 8, class_name: '初二(2)班', grade: '初二', mastery: 83, trend: 'up', weak: ['电路分析'] },
    { id: 15, name: '沈七', class_id: 9, classId: 9, class_name: '初三(1)班', grade: '初三', mastery: 76, trend: 'stable', weak: ['二次函数', '化学方程式'] },
    { id: 16, name: '韩八', class_id: 9, classId: 9, class_name: '初三(1)班', grade: '初三', mastery: 62, trend: 'down', weak: ['圆的证明', '欧姆定律', '酸碱盐'] },
    { id: 17, name: '杨九', class_id: 10, classId: 10, class_name: '初三(2)班', grade: '初三', mastery: 89, trend: 'up', weak: [] },
    { id: 18, name: '朱十', class_id: 10, classId: 10, class_name: '初三(2)班', grade: '初三', mastery: 70, trend: 'stable', weak: ['电功率', '化学计算'] },
  ]
}

function onNav(key) {
  const map = { students: '/teacher/students', tasks: '/teacher/tasks', upload: '/teacher/upload', exercise: '/teacher/exercise', me: '/teacher/me' }
  if (map[key]) router.push(map[key])
}

function goProfile(id) {
  router.push('/teacher/student/' + id)
}

onMounted(loadData)
</script>
