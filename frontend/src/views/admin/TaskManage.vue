<template>
  <div class="page">
    <PageHeader title="任务管理" />
    <div class="page-body">
      <div v-if="tasks.length === 0" style="text-align:center;color:var(--gray-400);padding:40px 20px">暂无任务</div>

      <div v-for="t in tasks" :key="t.id">
        <!-- Task Card -->
        <div class="card" style="margin-bottom:8px">
          <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div style="flex:1;min-width:0">
              <div style="font-weight:600;cursor:pointer" @click="toggleDetail(t)">{{ t.name }}</div>
              <div style="font-size:11px;color:var(--gray-400)">
                {{ t.type || '任务' }} · {{ t.subject || '' }} · {{ t.grade || '' }} · {{ formatDateText(t.created_at || t.createdAt) }}
              </div>
            </div>
            <StatusTag :status="t.status" type="task" />
          </div>
          <div v-if="t.objective" style="font-size:12px;color:var(--gray-500);margin-top:3px">
            {{ t.objective }}
          </div>
          <div v-if="t.total" style="margin-top:6px;display:flex;align-items:center;gap:6px">
            <div style="flex:1;height:4px;background:var(--gray-100);border-radius:2px">
              <div :style="{ width: ((t.confirmed || 0) / (t.total || 1) * 100) + '%', height: '100%', background: 'var(--primary)', borderRadius: '2px' }"></div>
            </div>
            <span style="font-size:11px;color:var(--gray-400)">{{ t.confirmed || 0 }}/{{ t.total }}</span>
          </div>
          <div style="margin-top:6px;display:flex;gap:4px;flex-wrap:wrap">
            <button class="btn btn-sm btn-outline" @click="toggleDetail(t)">
              {{ expandedTaskId === t.id ? '收起详情' : '详情' }}
            </button>
            <button v-if="t.status === 'ai_processing'" class="btn btn-sm btn-outline" @click="runAI(t)">
              重跑AI
            </button>
            <button class="btn btn-sm btn-outline" @click="handleEdit(t)">编辑</button>
            <button class="btn btn-sm btn-outline" style="color:var(--danger)" @click="handleDelete(t)">删除</button>
          </div>
        </div>

        <!-- Expanded Detail Card -->
        <div v-if="expandedTaskId === t.id" class="card fade-in" style="margin-bottom:8px;margin-top:-4px;background:var(--gray-50);border:1px solid var(--gray-200)">
          <!-- Basic Info -->
          <div style="font-size:13px;line-height:1.8;color:var(--gray-700)">
            <div><strong>任务名称：</strong>{{ t.name }}</div>
            <div><strong>任务类型：</strong>{{ t.type || '-' }}</div>
            <div><strong>学科：</strong>{{ t.subject || '-' }}</div>
            <div><strong>年级：</strong>{{ t.grade || '-' }}</div>
            <div><strong>难度：</strong>{{ difficultyStarsText(t.difficulty || 2) }}</div>
            <div v-if="t.pages"><strong>页数：</strong>{{ t.pages }}</div>
            <div v-if="t.objective"><strong>目标：</strong>{{ t.objective }}</div>
            <div><strong>创建人：</strong>{{ t.creator_name || t.creatorName || '-' }}</div>
            <div><strong>创建时间：</strong>{{ formatDateText(t.created_at || t.createdAt) }}</div>
          </div>

          <!-- Status Management -->
          <div style="margin-top:10px;padding-top:10px;border-top:1px solid var(--gray-200)">
            <div style="font-size:12px;color:var(--gray-500);margin-bottom:6px">状态管理</div>
            <div style="display:flex;gap:4px;flex-wrap:wrap;align-items:center">
              <StatusTag :status="t.status" type="task" />
              <button
                v-for="tr in getTransitions(t.status)"
                :key="tr.status"
                class="btn btn-sm"
                :class="tr.status === 'rejected' ? 'btn-danger' : 'btn-outline'"
                @click="handleStatusChange(t, tr.status)"
              >
                {{ tr.label }}
              </button>
              <span v-if="getTransitions(t.status).length === 0 && t.status !== 'completed'" style="font-size:11px;color:var(--gray-400)">无可用操作</span>
            </div>
          </div>

          <!-- Target Classes -->
          <div v-if="t.classes && t.classes.length" style="margin-top:10px;padding-top:10px;border-top:1px solid var(--gray-200)">
            <div style="font-size:12px;color:var(--gray-500);margin-bottom:4px">目标班级 ({{ t.classes.length }})</div>
            <div style="display:flex;gap:4px;flex-wrap:wrap">
              <span v-for="c in t.classes" :key="c.id || c" class="tag tag-primary">{{ c.name || c }}</span>
            </div>
          </div>

          <!-- Knowledge Points -->
          <div v-if="t.knowledge_points && t.knowledge_points.length" style="margin-top:10px;padding-top:10px;border-top:1px solid var(--gray-200)">
            <div style="font-size:12px;color:var(--gray-500);margin-bottom:4px">关联知识点 ({{ t.knowledge_points.length }})</div>
            <div style="display:flex;gap:4px;flex-wrap:wrap">
              <span v-for="kp in t.knowledge_points" :key="kp.id || kp" class="tag tag-gray">{{ kp.name || kp }}</span>
            </div>
          </div>

          <!-- Diagnosis Summary -->
          <div v-if="t.diagnoses && t.diagnoses.length" style="margin-top:10px;padding-top:10px;border-top:1px solid var(--gray-200)">
            <div style="font-size:12px;color:var(--gray-500);margin-bottom:4px">诊断摘要</div>
            <div style="font-size:12px;color:var(--gray-700)">
              共 {{ t.diagnoses.length }} 条诊断 ·
              已确认 {{ t.diagnoses.filter(d => d.verdict === 'correct' || d.status === 'confirmed').length }} ·
              待处理 {{ t.diagnoses.filter(d => d.verdict === 'uncertain' || d.status === 'pending').length }}
            </div>
            <button v-if="t.diagnosis_link || t.diagnosisLink" class="btn btn-sm btn-outline" style="margin-top:6px" @click="router.push(t.diagnosis_link || t.diagnosisLink)">
              查看诊断详情
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Edit Modal -->
    <CrudModal :show="showEditModal" title="编辑任务" @close="closeEditModal" @save="handleEditSave">
      <div class="input-group">
        <label>任务名称 <span style="color:var(--danger)">*</span></label>
        <input class="input" v-model="editForm.name" placeholder="请输入任务名称" />
        <div v-if="editErrors.name" style="font-size:11px;color:var(--danger);margin-top:2px">{{ editErrors.name }}</div>
      </div>
      <div class="input-group">
        <label>任务类型</label>
        <select class="input select" v-model="editForm.type">
          <option value="">请选择类型</option>
          <option v-for="t in TASK_TYPES" :value="t" :key="t">{{ t }}</option>
        </select>
      </div>
      <div class="input-group">
        <label>学科</label>
        <select class="input select" v-model="editForm.subject">
          <option value="">请选择学科</option>
          <option v-for="s in SUBJECTS" :value="s" :key="s">{{ s }}</option>
        </select>
      </div>
      <div class="input-group">
        <label>年级</label>
        <select class="input select" v-model="editForm.grade">
          <option value="">请选择年级</option>
          <option v-for="g in refStore.gradeNames" :value="g" :key="g">{{ g }}</option>
        </select>
      </div>
      <div class="input-group">
        <label>难度</label>
        <select class="input select" v-model.number="editForm.difficulty">
          <option :value="1">基础</option>
          <option :value="2">中等</option>
          <option :value="3">拔高</option>
        </select>
      </div>
      <div class="input-group">
        <label>页数</label>
        <input class="input" type="number" min="1" v-model.number="editForm.pages" placeholder="试卷页数" />
      </div>
      <div class="input-group">
        <label>任务目标</label>
        <textarea class="input textarea" v-model="editForm.objective" placeholder="描述任务目标"></textarea>
      </div>
      <div class="input-group">
        <label>目标班级</label>
        <div v-if="classList.length === 0" style="font-size:12px;color:var(--gray-400)">暂无班级数据</div>
        <div v-for="c in classList" :key="c.id" style="display:flex;align-items:center;gap:6px;padding:4px 0">
          <input type="checkbox" :value="c.id" v-model="editForm.class_ids" :id="'cls-' + c.id" />
          <label :for="'cls-' + c.id" style="font-size:13px;cursor:pointer">{{ c.name }}</label>
        </div>
      </div>
    </CrudModal>

    <BottomNav :items="navItems" active="tasks" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import BottomNav from '@/components/BottomNav.vue'
import StatusTag from '@/components/StatusTag.vue'
import CrudModal from '@/components/CrudModal.vue'
import { tasksAPI } from '@/api/tasks'
import { classesAPI } from '@/api/classes'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { icons } from '@/utils/icons'
import { formatDate, difficultyStars } from '@/utils/helpers'
import { TASK_TYPES, SUBJECTS, DIFFICULTY_LEVELS } from '@/utils/constants'
import { useReferenceStore } from '@/stores/reference'

const router = useRouter()
const authStore = useAuthStore()
const refStore = useReferenceStore()
const appStore = useAppStore()

const user = computed(() => authStore.user || JSON.parse(localStorage.getItem('user') || 'null'))
const role = computed(() => user.value?.role || 'admin')

const tasks = ref([])
const classList = ref([])

// Detail expansion
const expandedTaskId = ref(null)

// Edit modal
const showEditModal = ref(false)
const editingTask = ref(null)
const saving = ref(false)

const editForm = ref({
  name: '',
  type: '',
  subject: '',
  grade: '',
  difficulty: 2,
  pages: null,
  objective: '',
  class_ids: []
})

const editErrors = ref({})

const adminNav = [
  { key: 'dashboard', label: '总览', icon: icons.dashboard },
  { key: 'org', label: '组织', icon: icons.org },
  { key: 'tasks', label: '任务', icon: icons.tasks },
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

const navItems = computed(() => role.value === 'super' ? superNav : adminNav)

function showToast(msg) {
  appStore.showToast(msg)
}

function formatDateText(dateStr) {
  return formatDate(dateStr, 'YYYY-MM-DD')
}

function difficultyStarsText(n) {
  return difficultyStars(n)
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

// Status transitions
function getTransitions(status) {
  const transitions = {
    'draft': [{ status: 'pending_upload', label: '提交上传' }],
    'pending_upload': [
      { status: 'ai_processing', label: '开始AI批改' },
      { status: 'rejected', label: '驳回' }
    ],
    'ai_processing': [
      { status: 'pending_review', label: '完成AI批改' },
      { status: 'rejected', label: '驳回' }
    ],
    'pending_review': [
      { status: 'completed', label: '确认完成' },
      { status: 'rejected', label: '驳回重批' }
    ],
    'rejected': [{ status: 'draft', label: '重新提交' }],
    'completed': [],
    'partial_confirmed': [
      { status: 'completed', label: '确认完成' },
      { status: 'rejected', label: '驳回' }
    ]
  }
  return transitions[status] || []
}

async function handleStatusChange(task, newStatus) {
  const labelMap = {
    pending_upload: '提交上传',
    ai_processing: '开始AI批改',
    pending_review: '完成AI批改',
    completed: '确认完成',
    rejected: '驳回',
    draft: '重新提交'
  }
  const actionLabel = labelMap[newStatus] || newStatus
  if (!confirm(`确认${actionLabel}任务 "${task.name}"?`)) return
  try {
    await tasksAPI.updateStatus(task.id, newStatus)
    showToast(`任务状态已更新: ${actionLabel}`)
    await fetchTasks()
  } catch (e) {
    showToast('状态更新失败')
    console.warn('Status update failed:', e)
  }
}

// Detail toggle
function toggleDetail(t) {
  expandedTaskId.value = expandedTaskId.value === t.id ? null : t.id
}

// Edit handlers
function handleEdit(t) {
  editingTask.value = t
  editForm.value = {
    name: t.name || '',
    type: t.type || '',
    subject: t.subject || '',
    grade: t.grade || '',
    difficulty: t.difficulty || 2,
    pages: t.pages || null,
    objective: t.objective || '',
    class_ids: t.class_ids || t.classIds || (t.classes ? t.classes.map(c => c.id || c) : [])
  }
  editErrors.value = {}
  showEditModal.value = true
}

function closeEditModal() {
  showEditModal.value = false
  editingTask.value = null
}

function validateEditForm() {
  const errors = {}
  if (!editForm.value.name.trim()) errors.name = '请输入任务名称'
  editErrors.value = errors
  return Object.keys(errors).length === 0
}

async function handleEditSave() {
  if (!validateEditForm()) return
  if (saving.value || !editingTask.value) return
  saving.value = true

  const payload = {
    name: editForm.value.name.trim(),
    type: editForm.value.type || null,
    subject: editForm.value.subject || null,
    grade: editForm.value.grade || null,
    difficulty: editForm.value.difficulty,
    pages: editForm.value.pages,
    objective: editForm.value.objective || null,
    class_ids: editForm.value.class_ids || []
  }

  try {
    await tasksAPI.update(editingTask.value.id, payload)
    showToast('任务已更新')
    closeEditModal()
    await fetchTasks()
  } catch (e) {
    showToast('更新失败')
    console.warn('Update task failed:', e)
  } finally {
    saving.value = false
  }
}

// Delete
async function handleDelete(t) {
  if (!confirm('确认删除任务: ' + t.name + '?')) return
  try {
    await tasksAPI.remove(t.id)
    if (expandedTaskId.value === t.id) expandedTaskId.value = null
    await fetchTasks()
    showToast('已删除')
  } catch (e) {
    showToast('删除失败')
  }
}

// Run AI
async function runAI(t) {
  try {
    await tasksAPI.runAI(t.id)
    showToast('AI已重新运行')
    await fetchTasks()
  } catch (e) {
    showToast('操作失败')
  }
}

async function fetchTasks() {
  try {
    const res = await tasksAPI.getList()
    if (res && res.data) tasks.value = res.data
  } catch (e) {
    console.warn('Failed to fetch tasks:', e)
  }
}

async function fetchClasses() {
  try {
    const res = await classesAPI.getList()
    if (res && res.data) classList.value = res.data
  } catch (e) {
    console.warn('Failed to fetch classes:', e)
  }
}

onMounted(async () => {
  await refStore.fetchAll()
  fetchTasks()
  fetchClasses()
})
</script>
