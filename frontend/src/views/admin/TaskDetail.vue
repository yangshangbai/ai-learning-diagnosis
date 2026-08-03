<template>
  <div class="page">
    <PageHeader
      :title="task.name || '任务详情'"
      :showBack="true"
      backPath="/admin/tasks"
    />

    <div class="page-body">
      <!-- Loading -->
      <LoadSpinner v-if="loading" text="加载任务详情..." />

      <!-- Error -->
      <div v-else-if="error" style="text-align:center;color:var(--danger);padding:32px 16px">
        <div style="margin-bottom:8px">{{ error }}</div>
        <button class="btn btn-sm btn-outline" @click="fetchTask()">重试</button>
      </div>

      <!-- Task Content -->
      <template v-else-if="task.id">
        <!-- Task Info Card -->
        <div class="card">
          <div class="card-title-row">
            <h3 class="card-title">任务信息</h3>
            <StatusTag :status="task.status" type="task" />
          </div>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">任务名称</span>
              <span class="info-value">{{ task.name }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">任务类型</span>
              <span class="info-value">{{ task.type || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">学科</span>
              <span class="info-value">{{ task.subject || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">年级</span>
              <span class="info-value">{{ task.grade || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">难度</span>
              <span class="info-value">{{ difficultyStars(task.difficulty) }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">页数</span>
              <span class="info-value">{{ task.pages || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">创建人</span>
              <span class="info-value">{{ task.creator || task.created_by || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">创建时间</span>
              <span class="info-value">{{ formatDate(task.created_at || task.createdAt) }}</span>
            </div>
          </div>
          <div v-if="task.objective" class="info-item" style="margin-top:4px">
            <span class="info-label">任务目标</span>
            <span class="info-value" style="white-space:pre-wrap">{{ task.objective }}</span>
          </div>
        </div>

        <!-- Status Management -->
        <div class="card">
          <h3 class="card-title">状态管理</h3>
          <div class="status-bar">
            <div class="status-step" v-for="(s, idx) in statusSteps" :key="s.key"
              :class="{
                'status-done': statusIdx > idx,
                'status-current': statusIdx === idx,
                'status-pending': statusIdx < idx
              }">
              <span class="status-dot"></span>
              <span class="status-label">{{ s.label }}</span>
            </div>
          </div>
          <div v-if="nextTransitions.length > 0" class="transition-buttons">
            <button
              v-for="t in nextTransitions"
              :key="t.status"
              class="btn btn-sm"
              :class="t.btnClass || 'btn-primary'"
              @click="changeStatus(t.status)"
              :disabled="statusUpdating">
              {{ t.label }}
            </button>
          </div>
        </div>

        <!-- Target Classes -->
        <div v-if="task.classes && task.classes.length > 0" class="card">
          <h3 class="card-title">目标班级</h3>
          <div class="class-list">
            <div v-for="c in task.classes" :key="c.id || c.name" class="class-item">
              <span class="class-name">{{ c.name }}</span>
              <span class="class-count">{{ c.student_count || c.count || 0 }} 名学生</span>
            </div>
          </div>
        </div>

        <!-- Knowledge Points -->
        <div v-if="task.knowledge_points && task.knowledge_points.length > 0" class="card">
          <h3 class="card-title">知识点</h3>
          <div class="tag-list">
            <span v-for="kp in task.knowledge_points" :key="kp" class="tag tag-primary">{{ kp }}</span>
          </div>
        </div>

        <!-- Diagnosis Summary -->
        <div v-if="diagnoses.length > 0" class="card">
          <h3 class="card-title">诊断批改进度</h3>
          <div class="kpi-row">
            <KpiCard label="总诊断数" :value="diagnosisStats.total" />
            <KpiCard label="已确认" :value="diagnosisStats.confirmed" color="var(--success)" />
            <KpiCard label="待确认" :value="diagnosisStats.pending" color="var(--warning)" />
          </div>
          <div class="progress-wrap">
            <div class="progress-bar">
              <div class="progress-fill"
                :style="{ width: diagnosisStats.percent + '%' }"></div>
            </div>
            <span class="progress-text">{{ diagnosisStats.confirmed }}/{{ diagnosisStats.total }}</span>
          </div>

          <!-- Student Diagnosis List -->
          <div class="student-diag-list">
            <div v-for="d in diagnoses" :key="d.id" class="diag-item">
              <div class="diag-left">
                <span class="diag-student">{{ d.student_name || d.student || '未知' }}</span>
                <StatusTag :status="d.status" type="task" />
              </div>
              <router-link
                v-if="role === 'teacher'"
                :to="'/teacher/grading/' + task.id"
                class="diag-link">查看批改</router-link>
              <router-link
                v-else
                :to="'/admin/diagnosis?task_id=' + task.id"
                class="diag-link">查看诊断看板</router-link>
            </div>
          </div>
        </div>

        <!-- Empty Diagnosis -->
        <div v-else-if="task.status === 'ai_processing' || task.status === 'pending_review' || task.status === 'completed' || task.status === 'partial_confirmed'" class="card">
          <div style="text-align:center;color:var(--gray-400);padding:20px 0">
            暂无诊断数据
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="action-bar">
          <button
            v-if="task.status === 'ai_processing' || task.status === 'pending_review'"
            class="btn btn-outline"
            @click="runAI"
            :disabled="runningAI">
            {{ runningAI ? '处理中...' : '重跑AI' }}
          </button>
          <button class="btn btn-outline" @click="openEdit">编辑</button>
          <button class="btn btn-outline" style="color:var(--danger);border-color:var(--danger)" @click="handleDelete">删除</button>
        </div>
      </template>
    </div>

    <!-- Edit Modal -->
    <CrudModal
      :show="showEditModal"
      title="编辑任务"
      @close="showEditModal = false"
      @save="saveEdit">
      <div class="form-group">
        <label class="form-label">任务名称</label>
        <input class="input" v-model="editForm.name" placeholder="输入任务名称" />
      </div>
      <div class="form-group">
        <label class="form-label">任务类型</label>
        <input class="input" v-model="editForm.type" placeholder="如：周测、月考" />
      </div>
      <div class="form-group">
        <label class="form-label">学科</label>
        <input class="input" v-model="editForm.subject" placeholder="如：数学" />
      </div>
      <div class="form-group">
        <label class="form-label">年级</label>
        <input class="input" v-model="editForm.grade" placeholder="如：高二" />
      </div>
      <div class="form-group">
        <label class="form-label">难度 (1-3)</label>
        <input class="input" type="number" min="1" max="3" v-model.number="editForm.difficulty" />
      </div>
      <div class="form-group">
        <label class="form-label">页数</label>
        <input class="input" type="number" min="1" v-model.number="editForm.pages" />
      </div>
      <div class="form-group">
        <label class="form-label">任务目标</label>
        <textarea class="input" rows="3" v-model="editForm.objective" placeholder="输入任务目标"></textarea>
      </div>
    </CrudModal>

    <BottomNav :items="navItems" active="tasks" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import BottomNav from '@/components/BottomNav.vue'
import StatusTag from '@/components/StatusTag.vue'
import KpiCard from '@/components/KpiCard.vue'
import LoadSpinner from '@/components/LoadSpinner.vue'
import CrudModal from '@/components/CrudModal.vue'
import { tasksAPI } from '@/api/tasks'
import { diagnosesAPI } from '@/api/diagnoses'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { icons } from '@/utils/icons'
import { formatDate, difficultyStars } from '@/utils/helpers'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const appStore = useAppStore()

const user = computed(() => authStore.user || JSON.parse(localStorage.getItem('user') || 'null'))
const role = computed(() => user.value?.role || 'admin')

const task = ref({})
const loading = ref(true)
const error = ref('')
const statusUpdating = ref(false)
const runningAI = ref(false)

const diagnoses = ref([])
const showEditModal = ref(false)
const editForm = reactive({
  name: '', type: '', subject: '', grade: '', difficulty: 1, pages: 1, objective: ''
})

// Status state machine
const statusSteps = [
  { key: 'draft', label: '草稿' },
  { key: 'pending_upload', label: '待上传' },
  { key: 'ai_processing', label: 'AI批改中' },
  { key: 'pending_review', label: '待确认' },
  { key: 'completed', label: '已完成' }
]

const statusIdx = computed(() => {
  const idx = statusSteps.findIndex(s => s.key === task.value.status)
  return idx >= 0 ? idx : 0
})

const nextTransitions = computed(() => {
  const map = {
    draft: [{ status: 'pending_upload', label: '进入待上传', btnClass: 'btn-primary' }],
    pending_upload: [{ status: 'ai_processing', label: '开始AI批改', btnClass: 'btn-primary' }],
    ai_processing: [{ status: 'pending_review', label: '批改完成，进入待确认', btnClass: 'btn-success' }],
    pending_review: [{ status: 'completed', label: '确认完成', btnClass: 'btn-success' }],
    completed: [],
    rejected: [{ status: 'draft', label: '退回草稿', btnClass: 'btn-outline' }],
    partial_confirmed: [{ status: 'completed', label: '强制完成', btnClass: 'btn-success' }]
  }
  return map[task.value.status] || []
})

const diagnosisStats = computed(() => {
  const total = diagnoses.value.length
  const confirmed = diagnoses.value.filter(d => d.status === 'completed' || d.status === 'confirmed').length
  const pending = total - confirmed
  const percent = total > 0 ? parseFloat(((confirmed / total) * 100).toFixed(1)) : 0
  return { total, confirmed, pending, percent }
})

const adminNav = [
  { key: 'dashboard', label: '总览', icon: icons.dashboard },
  { key: 'org', label: '组织', icon: icons.org },
  { key: 'tasks', label: '任务', icon: icons.tasks },
  { key: 'diagnosis', label: '诊断', icon: icons.diagnosis },
  { key: 'me', label: '我的', icon: icons.home }
]

const researchNav = [
  { key: 'knowledge', label: '知识库', icon: icons.knowledge },
  { key: 'qbank', label: '题库', icon: icons.qbank },
  { key: 'ai', label: 'AI', icon: icons.ai },
  { key: 'diagnosis', label: '诊断', icon: icons.diagnosis },
  { key: 'me', label: '我的', icon: icons.home }
]

const superNav = [
  { key: 'dashboard', label: '总览', icon: icons.dashboard },
  { key: 'org', label: '组织', icon: icons.org },
  { key: 'system', label: '系统', icon: icons.settings },
  { key: 'diagnosis', label: '诊断', icon: icons.diagnosis },
  { key: 'me', label: '我的', icon: icons.home }
]

const navItems = computed(() => {
  if (role.value === 'research') return researchNav
  return role.value === 'super' ? superNav : adminNav
})

function showToast(msg) {
  appStore.showToast(msg)
}

function onNav(key) {
  const map = {
    dashboard: '/admin/dashboard',
    org: '/admin/org',
    tasks: '/admin/tasks',
    diagnosis: '/admin/diagnosis',
    system: '/admin/system',
    me: '/admin/me'
  }
  if (map[key]) router.push(map[key])
}

async function fetchTask() {
  const id = route.params.id
  if (!id) {
    error.value = '任务ID无效'
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  try {
    const res = await tasksAPI.getById(id)
    task.value = res.data || res
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '加载任务失败'
  } finally {
    loading.value = false
  }
}

async function fetchDiagnoses() {
  const id = route.params.id
  if (!id) return
  try {
    const res = await diagnosesAPI.getList({ task_id: id })
    diagnoses.value = res.data?.items || res.data || res || []
  } catch (e) {
    console.warn('Failed to fetch diagnoses:', e)
  }
}

async function changeStatus(newStatus) {
  statusUpdating.value = true
  try {
    await tasksAPI.updateStatus(task.value.id, newStatus)
    task.value.status = newStatus
    showToast('状态已更新')
  } catch (e) {
    showToast('状态更新失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    statusUpdating.value = false
  }
}

async function runAI() {
  runningAI.value = true
  try {
    await tasksAPI.runAI(task.value.id)
    task.value.status = 'ai_processing'
    showToast('AI重新处理已启动')
  } catch (e) {
    showToast('操作失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    runningAI.value = false
  }
}

function openEdit() {
  editForm.name = task.value.name || ''
  editForm.type = task.value.type || ''
  editForm.subject = task.value.subject || ''
  editForm.grade = task.value.grade || ''
  editForm.difficulty = task.value.difficulty || 1
  editForm.pages = task.value.pages || 1
  editForm.objective = task.value.objective || ''
  showEditModal.value = true
}

async function saveEdit() {
  try {
    await tasksAPI.update(task.value.id, {
      name: editForm.name,
      type: editForm.type,
      subject: editForm.subject,
      grade: editForm.grade,
      difficulty: editForm.difficulty,
      pages: editForm.pages,
      objective: editForm.objective
    })
    showToast('更新成功')
    showEditModal.value = false
    await fetchTask()
  } catch (e) {
    showToast('更新失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function handleDelete() {
  if (!confirm('确认删除任务: ' + task.value.name + '?')) return
  try {
    await tasksAPI.remove(task.value.id)
    showToast('已删除')
    router.push('/admin/tasks')
  } catch (e) {
    showToast('删除失败: ' + (e.response?.data?.detail || e.message))
  }
}

onMounted(() => {
  fetchTask()
  fetchDiagnoses()
})
</script>

<style scoped>
.card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 10px 0;
  color: var(--gray-900);
}
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 12px;
}
.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.info-label {
  font-size: 11px;
  color: var(--gray-400);
}
.info-value {
  font-size: 13px;
  color: var(--gray-700);
  font-weight: 500;
}

/* Status Bar */
.status-bar {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
  position: relative;
}
.status-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  position: relative;
}
.status-step::after {
  content: '';
  position: absolute;
  top: 8px;
  left: 50%;
  width: 100%;
  height: 2px;
  background: var(--gray-200);
  z-index: 0;
}
.status-step:last-child::after {
  display: none;
}
.status-done::after {
  background: var(--primary);
}
.status-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid var(--gray-300);
  background: #fff;
  z-index: 1;
  flex-shrink: 0;
}
.status-done .status-dot {
  background: var(--primary);
  border-color: var(--primary);
}
.status-current .status-dot {
  border-color: var(--primary);
  background: var(--primary-light);
}
.status-label {
  font-size: 10px;
  color: var(--gray-400);
  margin-top: 4px;
  white-space: nowrap;
}
.status-done .status-label,
.status-current .status-label {
  color: var(--primary);
  font-weight: 600;
}

.transition-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* Class List */
.class-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.class-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--gray-50);
  border-radius: var(--radius-sm);
}
.class-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--gray-700);
}
.class-count {
  font-size: 11px;
  color: var(--gray-400);
}

/* Tag List */
.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}
.tag-primary {
  background: var(--primary-light);
  color: var(--primary);
}

/* KPI Row */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 12px;
}

/* Progress */
.progress-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.progress-bar {
  flex: 1;
  height: 8px;
  background: var(--gray-100);
  border-radius: 4px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: var(--primary);
  border-radius: 4px;
  transition: width .3s ease;
}
.progress-text {
  font-size: 12px;
  color: var(--gray-500);
  white-space: nowrap;
}

/* Student Diagnosis List */
.student-diag-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.diag-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--gray-100);
}
.diag-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.diag-student {
  font-size: 13px;
  color: var(--gray-700);
}
.diag-link {
  font-size: 12px;
  color: var(--primary);
  text-decoration: none;
  font-weight: 500;
}

/* Action Bar */
.action-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
  margin-bottom: 60px;
}
.action-bar .btn {
  flex: 1;
  min-width: 80px;
}

/* Form */
.form-group {
  margin-bottom: 12px;
}
.form-label {
  display: block;
  font-size: 12px;
  color: var(--gray-500);
  margin-bottom: 4px;
  font-weight: 500;
}
.input {
  width: 100%;
  height: 40px;
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-sm);
  padding: 0 12px;
  font-size: 14px;
  box-sizing: border-box;
}
textarea.input {
  height: auto;
  padding: 10px 12px;
  resize: vertical;
}
</style>
