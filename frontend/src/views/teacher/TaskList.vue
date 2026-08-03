<template>
  <div class="page">
    <PageHeader title="我的任务">
      <template #actions>
        <button class="btn btn-sm btn-primary" @click="openCreate">+ 新建</button>
      </template>
    </PageHeader>

    <div class="page-body">
      <LoadSpinner v-if="loading" text="加载任务列表..." />

      <template v-else>
        <div v-for="t in myTasks" :key="t.id" class="card fade-in">
          <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div>
              <div style="font-weight:600">{{ t.name }}</div>
              <div style="font-size:11px;color:var(--gray-400);margin-top:2px">{{ t.type }} · {{ t.subject }} · {{ t.grade }} · {{ t.createdAt || t.created_at }}</div>
            </div>
            <StatusTag :status="t.status" type="task" />
          </div>
          <div style="font-size:12px;color:var(--gray-500);margin-top:4px">&#x1F3AF; {{ t.objective }}</div>
          <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:4px">
            <span v-for="kp in (t.kps || [])" :key="kp" class="tag tag-primary" style="font-size:10px">{{ kp }}</span>
          </div>
          <div v-if="t.total" style="margin-top:8px;display:flex;align-items:center;gap:8px">
            <div style="flex:1;height:4px;background:var(--gray-100);border-radius:2px">
              <div :style="{width: (t.confirmed / t.total * 100) + '%',height:'100%',background:'var(--primary)',borderRadius:'2px'}"></div>
            </div>
            <span style="font-size:11px;color:var(--gray-400)">{{ t.confirmed }}/{{ t.total }}</span>
          </div>
          <div style="margin-top:8px;display:flex;gap:6px">
            <button v-if="t.status === 'draft'" class="btn btn-sm btn-outline" @click="editTask(t)">&#x270F;&#xFE0F; 编辑</button>
            <button v-if="t.status === 'pending_upload' || t.status === 'draft'" class="btn btn-sm btn-primary" @click="goUpload(t)">&#x1F4E4; 上传试卷</button>
            <button v-if="t.status === 'pending_review'" class="btn btn-sm btn-primary" @click="goReview(t)">&#x1F50D; 确认批改</button>
            <button class="btn btn-sm btn-outline" @click="viewDetail(t)">详情</button>
            <button class="btn btn-sm btn-outline" style="color:var(--danger)" @click="deleteTaskFunc(t)">&#x1F5D1;&#xFE0F;</button>
          </div>
        </div>

        <!-- Inline Detail Card -->
        <div v-if="detailTask" class="card" style="background:var(--gray-50);border:1px solid var(--primary);margin-top:12px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <div style="font-weight:600;font-size:14px;color:var(--primary)">&#x1F4CB; 任务详情</div>
            <button class="btn btn-sm btn-outline" @click="detailTask = null">&#x2715;</button>
          </div>
          <div style="font-size:13px;line-height:1.8">
            <div><b>任务名称：</b>{{ detailTask.name }}</div>
            <div><b>任务类型：</b>{{ detailTask.type }} · {{ detailTask.subject }} · {{ detailTask.grade }}</div>
            <div><b>班级：</b>{{ (detailTask.classIds || []).map(cid => { const cls = allClasses.find(x => x.id === cid); return cls ? cls.name : cid }).join('、') }}</div>
            <div><b>试卷页数：</b>{{ detailTask.pages }} 页</div>
            <div><b>任务目标：</b>{{ detailTask.objective }}</div>
            <div><b>难度预设：</b>{{ detailTask.difficulty }}</div>
            <div><b>知识点：</b>
              <span v-for="kp in (detailTask.kps || [])" :key="kp" class="tag tag-primary" style="font-size:10px;margin-right:3px">{{ kp }}</span>
              <span v-if="!(detailTask.kps || []).length" style="color:var(--gray-400)">--</span>
            </div>
            <div><b>状态：</b><StatusTag :status="detailTask.status" type="task" style="margin-left:4px" /></div>
            <div><b>创建时间：</b>{{ detailTask.createdAt || detailTask.created_at }}</div>
          </div>
          <div style="display:flex;gap:6px;margin-top:10px">
            <button v-if="detailTask.status === 'draft'" class="btn btn-sm btn-outline" @click="editTask(detailTask); detailTask = null">&#x270F;&#xFE0F; 编辑</button>
            <button v-if="detailTask.status === 'pending_upload' || detailTask.status === 'draft'" class="btn btn-sm btn-primary" @click="goUpload(detailTask)">&#x1F4E4; 上传试卷</button>
            <button v-if="detailTask.status === 'pending_review'" class="btn btn-sm btn-primary" @click="goReview(detailTask)">&#x1F50D; 确认批改</button>
          </div>
        </div>

        <EmptyState
          v-if="!loading && myTasks.length === 0"
          icon="&#x1F4CB;" title="暂无任务"
          desc="点击右上角新建任务"
          @action="openCreate"
          action="新建任务"
        />
      </template>

      <!-- Create Task Modal -->
      <CrudModal :show="showModal" :title="modalTitle" @close="closeModal" @save="saveTask">
        <div class="input-group">
          <label>任务名称</label>
          <input class="input" v-model="newTask.name" placeholder="如：第三单元周测-分数" />
        </div>
        <div class="input-group">
          <label>任务类型</label>
          <select class="input select" v-model="newTask.type">
            <option v-for="t in taskTypes" :value="t" :key="t">{{ t }}</option>
          </select>
        </div>
        <div class="input-group">
          <label>学科</label>
          <select class="input select" v-model="newTask.subject">
            <option v-for="s in subjects" :value="s" :key="s">{{ s }}</option>
          </select>
        </div>
        <div class="input-group">
          <label>年级</label>
          <select class="input select" v-model="newTask.grade" @change="newTask.classIds = []">
            <option v-for="g in grades" :value="g" :key="g">{{ g }}</option>
          </select>
        </div>
        <div class="input-group">
          <label>班级</label>
          <div style="display:flex;flex-wrap:wrap;gap:6px">
            <label v-for="c in availableClasses" :key="c.id" style="font-size:13px;cursor:pointer">
              <input type="checkbox" :value="c.id" v-model="newTask.classIds" /> {{ c.name }}
            </label>
          </div>
        </div>
        <div class="input-group">
          <label>试卷页数</label>
          <input class="input" type="number" v-model.number="newTask.pages" min="1" max="8" />
        </div>
        <div class="input-group">
          <label>任务目标</label>
          <textarea class="textarea" v-model="newTask.objective" placeholder="本次测试希望检测什么？如：检测分数加减法的掌握情况"></textarea>
        </div>
        <div class="input-group">
          <label>难度预设</label>
            <select class="input select" v-model="newTask.difficulty">
            <option v-for="d in DIFFICULTY_LEVELS" :key="d">{{ d }}</option>
          </select>
        </div>
      </CrudModal>
    </div>

    <BottomNav :items="teacherNav" active="tasks" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { tasksAPI } from '@/api/tasks'
import { classesAPI } from '@/api/classes'
import BottomNav from '@/components/BottomNav.vue'
import PageHeader from '@/components/PageHeader.vue'
import CrudModal from '@/components/CrudModal.vue'
import StatusTag from '@/components/StatusTag.vue'
import LoadSpinner from '@/components/LoadSpinner.vue'
import EmptyState from '@/components/EmptyState.vue'
import { TASK_TYPES, SUBJECTS, DIFFICULTY_LEVELS } from '@/utils/constants'
import { useReferenceStore } from '@/stores/reference'
import { icons } from '@/utils/icons'
import { statusLabel } from '@/utils/helpers'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()
const refStore = useReferenceStore()

const loading = ref(true)
const tasks = ref([])
const allClasses = ref([])
const showModal = ref(false)
const editingId = ref(null)
const detailTask = ref(null)

const taskTypes = TASK_TYPES
const subjects = SUBJECTS
const grades = computed(() => refStore.gradeNames)

const defaultTask = () => ({
  name: '', type: '日常作业', subject: '数学', grade: '五年级',
  classIds: [], pages: 4, objective: '', difficulty: '中等'
})

const newTask = ref(defaultTask())

const user = computed(() => authStore.user)

const modalTitle = computed(() => editingId.value ? '编辑任务' : '新建任务')

const availableClasses = computed(() => {
  const gradeName = newTask.value.grade
  const userClassIds = (user.value?.classes || []).map(c => Number(c))
  let list = allClasses.value.filter(c => (c.grade_name || c.grade) === gradeName)
  // If teacher has class restrictions, only show their own classes
  if (userClassIds.length > 0) {
    list = list.filter(c => userClassIds.includes(Number(c.id)))
  }
  return list
})

const myTasks = computed(() => {
  if (!user.value?.classes) return tasks.value
  return tasks.value.filter(t => user.value.classes.some(c => (t.classIds || t.class_ids || []).includes(c)))
})

const teacherNav = [
  { key: 'students', label: '学生', icon: icons.students },
  { key: 'tasks', label: '任务', icon: icons.tasks },
  { key: 'upload', label: '上传', icon: icons.upload },
  { key: 'exercise', label: '练习', icon: icons.exercise },
  { key: 'me', label: '我的', icon: icons.home },
]

function onNav(key) {
  const map = { students: '/teacher/students', tasks: '/teacher/tasks', upload: '/teacher/upload', exercise: '/teacher/exercise', me: '/teacher/me' }
  if (key === 'students') router.push('/teacher/students')
  else if (key === 'upload') router.push('/teacher/upload')
  else if (key === 'exercise') router.push('/teacher/exercise')
  else if (key === 'me') router.push('/teacher/me')
}

async function loadData() {
  loading.value = true
  await refStore.fetchAll()
  try {
    const [taskRes, classRes] = await Promise.allSettled([
      tasksAPI.getList(),
      classesAPI.getList(),
    ])
    if (taskRes.status === 'fulfilled') {
      const r = taskRes.value; tasks.value = r?.items || r?.data || r || []
    } else {
      tasks.value = getMockTasks()
    }
    if (classRes.status === 'fulfilled') {
      const r = classRes.value; allClasses.value = r?.items || r?.data || r || []
    } else {
      allClasses.value = getMockClasses()
    }
  } catch {
    tasks.value = getMockTasks()
    allClasses.value = getMockClasses()
  } finally {
    loading.value = false
  }
}

function getMockTasks() {
  return [
    { id: 1, name: '第三单元周测-分数', type: '周测', subject: '数学', grade: '五年级', classIds: [1, 2], pages: 4, objective: '检测分数加减法和分数基本概念的掌握情况', kps: ['分数概念', '同分母分数加减', '异分母分数加减', '分数比较'], difficulty: '中等', status: 'pending_review', confirmed: 8, total: 15, createdAt: '07/15' },
    { id: 2, name: '日常作业-三角形全等', type: '日常作业', subject: '数学', grade: '五年级', classIds: [1], pages: 2, objective: '巩固三角形全等判定定理的运用', kps: ['三角形全等', '三角形面积'], difficulty: '基础', status: 'ai_processing', confirmed: 0, total: 8, createdAt: '07/16' },
    { id: 3, name: '专项练习-分数应用题', type: '专项练习', subject: '数学', grade: '五年级', classIds: [2], pages: 4, objective: '强化分数在实际问题中的建模能力', kps: ['分数应用题建模', '分数四则混合运算'], difficulty: '拔高', status: 'pending_upload', confirmed: 0, total: 0, createdAt: '07/17' },
    { id: 4, name: '阶段测-电路分析', type: '阶段测', subject: '物理', grade: '初二', classIds: [7, 8], pages: 6, objective: '检测欧姆定律和电路分析的综合运用', kps: ['欧姆定律', '串并联电路', '电功率'], difficulty: '中等', status: 'pending_review', confirmed: 5, total: 20, createdAt: '07/14' },
    { id: 5, name: '期末模拟-数学', type: '期末模拟', subject: '数学', grade: '初三', classIds: [9, 10], pages: 8, objective: '全真模拟中考数学', kps: ['二次函数', '圆的证明', '概率统计', '三角函数'], difficulty: '拔高', status: 'draft', confirmed: 0, total: 0, createdAt: '07/17' },
  ]
}

function getMockClasses() {
  return [
    { id: 1, name: '五(1)班', grade: '五年级', subjects: ['数学'] },
    { id: 2, name: '五(2)班', grade: '五年级', subjects: ['数学'] },
    { id: 7, name: '初二(1)班', grade: '初二', subjects: ['数学', '物理'] },
    { id: 8, name: '初二(2)班', grade: '初二', subjects: ['数学', '物理'] },
    { id: 9, name: '初三(1)班', grade: '初三', subjects: ['数学', '物理', '化学'] },
    { id: 10, name: '初三(2)班', grade: '初三', subjects: ['数学', '物理', '化学'] },
  ]
}

function goUpload(t) {
  router.push('/teacher/upload?taskId=' + t.id)
}

function goReview(t) {
  router.push('/teacher/grading/' + t.id)
}

function viewDetail(t) {
  detailTask.value = detailTask.value?.id === t.id ? null : t
}

function openCreate() {
  editingId.value = null
  newTask.value = defaultTask()
  showModal.value = true
}

function editTask(t) {
  editingId.value = t.id
  newTask.value = {
    name: t.name,
    type: t.type,
    subject: t.subject,
    grade: t.grade,
    classIds: [...(t.classIds || t.class_ids || [])],
    pages: t.pages,
    objective: t.objective,
    difficulty: t.difficulty,
  }
  showModal.value = true
}

async function deleteTaskFunc(t) {
  if (!confirm('确定删除任务"' + t.name + '"?')) return
  try {
    await tasksAPI.remove(t.id)
  } catch {
    // ignore
  }
  tasks.value = tasks.value.filter(x => x.id !== t.id)
  if (detailTask.value?.id === t.id) detailTask.value = null
  appStore.showToast('任务已删除')
}

function closeModal() {
  showModal.value = false
  editingId.value = null
  newTask.value = defaultTask()
}

async function saveTask() {
  if (!newTask.value.name.trim()) {
    appStore.showToast('请输入任务名称')
    return
  }
  if (!newTask.value.classIds.length) {
    if (availableClasses.value.length === 0) {
      appStore.showToast('未加载到可用班级，请刷新页面后重试')
    } else {
      appStore.showToast('请至少选择一个班级')
    }
    return
  }

  const payload = {
    name: newTask.value.name,
    type: newTask.value.type,
    subject: newTask.value.subject,
    grade: newTask.value.grade,
    class_ids: [...newTask.value.classIds],
    pages: newTask.value.pages,
    objective: newTask.value.objective,
    difficulty: newTask.value.difficulty,
  }

  if (editingId.value) {
    // Edit mode
    try {
      await tasksAPI.update(editingId.value, payload)
      const idx = tasks.value.findIndex(x => x.id === editingId.value)
      if (idx >= 0) {
        tasks.value[idx] = {
          ...tasks.value[idx],
          ...payload,
          classIds: [...newTask.value.classIds],
        }
      }
      appStore.showToast('任务已更新')
    } catch {
      appStore.showToast('更新失败，请重试')
    }
  } else {
    // Create mode
    try {
      const res = await tasksAPI.create(payload)
      const created = res.data || res || {}
      tasks.value.unshift({
        id: created.id || 'tk' + Date.now(),
        ...payload,
        classIds: [...newTask.value.classIds],
        kps: [],
        status: 'draft',
        confirmed: 0,
        total: 0,
        createdAt: new Date().toLocaleDateString('zh', { month: 'short', day: 'numeric' }),
      })
    } catch {
      tasks.value.unshift({
        id: 'tk' + Date.now(),
        name: newTask.value.name,
        type: newTask.value.type,
        subject: newTask.value.subject,
        grade: newTask.value.grade,
        classIds: [...newTask.value.classIds],
        pages: newTask.value.pages,
        objective: newTask.value.objective,
        kps: [],
        difficulty: newTask.value.difficulty,
        status: 'draft',
        confirmed: 0,
        total: 0,
        createdAt: new Date().toLocaleDateString('zh', { month: 'short', day: 'numeric' }),
      })
    }
    appStore.showToast('任务已创建')
  }
  closeModal()
}

onMounted(loadData)
</script>
