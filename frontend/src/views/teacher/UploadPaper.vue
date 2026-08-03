<template>
  <div class="page">
    <PageHeader title="上传试卷" :showBack="true" backPath="/teacher/tasks" />

    <div class="page-body">
      <!-- Step 1: Select Task -->
      <div v-if="step === 1" class="fade-in">
        <div class="card" style="background:var(--primary-light)">
          <div style="font-weight:600;font-size:14px">&#x1F4CC; 选择任务</div>
          <div style="font-size:11px;color:var(--gray-500);margin-top:2px">支持 JPG/PNG/PDF/Word，单文件最大50MB</div>
        </div>
        <div v-for="t in pendingTasks" :key="t.id" class="card" style="cursor:pointer" @click="selectTask(t)">
          <div style="font-weight:600">{{ t.name }}</div>
          <div style="font-size:11px;color:var(--gray-400);margin-top:2px">{{ t.type }} · {{ t.subject }} · {{ t.grade }} · {{ t.createdAt || t.created_at }}</div>
          <StatusTag :status="t.status" type="task" style="margin-top:4px" />
        </div>
        <EmptyState v-if="!loading && !pendingTasks.length" icon="&#x1F4E4;" title="没有待上传的任务" desc="请先在任务页面创建任务" @action="$router.push('/teacher/tasks')" action="去创建任务" />
      </div>

      <!-- Step 2: Upload -->
      <div v-if="step === 2" class="fade-in">
        <div class="card" style="background:var(--primary-light);border-color:var(--primary)">
          <div style="font-size:12px;color:var(--primary);font-weight:600">&#x1F4CB; 已选: {{ selTask?.name }} ({{ pageCount }}面)</div>
          <button class="btn btn-sm btn-outline" style="margin-top:4px" @click="step = 1">更换任务</button>
        </div>

        <!-- Step 2a: Upload Answer Key -->
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <div style="font-weight:600;font-size:14px">第一步：上传标准答案</div>
            <span class="tag" :class="answerFileCount > 0 ? 'tag-green' : 'tag-yellow'">已传 {{ answerFileCount }} 份</span>
          </div>
          <p style="font-size:12px;color:var(--gray-500);margin-bottom:8px">上传标准答案图片/PDF，支持多图一次性选择</p>

          <!-- Drag & Drop Zone -->
          <div
            class="drop-zone"
            :class="{ 'drop-active': answerDragOver }"
            @dragover.prevent="answerDragOver = true"
            @dragleave.prevent="answerDragOver = false"
            @drop.prevent="onAnswerDrop"
            @click="triggerAnswerInput()"
          >
            <div style="font-size:28px">&#x1F4C4;</div>
            <div style="font-size:13px;margin-top:4px">点击或拖拽文件到此处</div>
            <div style="font-size:11px;color:var(--gray-400)">JPG / PNG / PDF / Word · 单文件≤50MB</div>
            <input
              type="file"
              ref="ansInput"
              accept="image/*,.pdf,.doc,.docx"
              multiple
              style="display:none"
              @change="onAnswerFilesSelected"
            />
          </div>

          <!-- Answer Preview Grid -->
          <div v-if="answerList.length" style="margin-top:10px">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
              <span style="font-size:12px;font-weight:600">已上传答案 ({{ answerList.length }})</span>
              <button class="btn btn-sm btn-outline" @click="clearAnswerFiles" style="font-size:11px">清空</button>
              <span style="font-size:10px;color:var(--gray-400)">拖拽排序</span>
            </div>
            <div class="preview-grid">
              <div
                v-for="(item, idx) in answerList"
                :key="idx"
                class="preview-item"
                :class="{ 'is-pdf': isDocType(item) }"
                draggable="true"
                @dragstart="onAnswerDragStart(idx)"
                @dragover.prevent="onAnswerDragOver(idx)"
                @drop.prevent="onAnswerDropReorder(idx)"
                @dragend="answerDragIdx = null"
              >
                <img v-if="item.preview" :src="item.preview" @error="e => e.target.style.display='none'" />
                <div v-else class="doc-icon">&#x1F4C4;</div>
                <div class="preview-label">{{ item.name }}</div>
                <div class="preview-size">{{ formatSize(item.file?.size || 0) }}</div>
                <button class="preview-remove" @click.stop="removeAnswer(idx)">&#x2715;</button>
                <div v-if="idx === answerDragOverIdx && answerDragIdx !== idx" class="drop-indicator"></div>
              </div>
            </div>
          </div>
        </div>

        <!-- Step 2b: Upload Student Papers -->
        <div class="card" v-if="answerFileCount > 0">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <div style="font-weight:600;font-size:14px">第二步：上传学生试卷</div>
            <span class="tag" :class="studentFileCount > 0 ? 'tag-green' : 'tag-yellow'">已传 {{ studentFileCount }} 份</span>
          </div>

          <div class="input-group">
            <label>选择学生</label>
            <select class="input select" v-model="selStudentId" @change="onStudentChange">
              <option value="">-- 请选择学生 --</option>
              <option v-for="s in taskStudents" :value="s.id" :key="s.id">{{ s.name }} · {{ s.class_name || s.className || '班级' + s.class_id }}</option>
            </select>
            <div v-if="selTask && !taskStudents.length" style="font-size:11px;color:var(--warning);margin-top:4px">
              ⚠ 该任务关联的班级中没有学生数据，或学生不在您的班级范围内
            </div>
          </div>

          <template v-if="selStudentId">
            <p style="font-size:12px;color:var(--gray-500);margin-bottom:8px">上传该学生的试卷图片/PDF</p>
            <div
              class="drop-zone"
              :class="{ 'drop-active': studentDragOver }"
              @dragover.prevent="studentDragOver = true"
              @dragleave.prevent="studentDragOver = false"
              @drop.prevent="onStudentDrop"
              @click="triggerStudentInput()"
            >
              <div style="font-size:28px">&#x1F4C4;</div>
              <div style="font-size:13px;margin-top:4px">点击或拖拽学生试卷</div>
              <input
                type="file"
                ref="stuInput"
                accept="image/*,.pdf,.doc,.docx"
                multiple
                style="display:none"
                @change="onStudentFilesSelected"
              />
            </div>

            <div v-if="studentList.length" style="margin-top:10px">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
                <span style="font-size:12px;font-weight:600">已上传试卷 ({{ studentList.length }})</span>
                <button class="btn btn-sm btn-outline" @click="clearStudentFiles" style="font-size:11px">清空</button>
                <span style="font-size:10px;color:var(--gray-400)">拖拽排序</span>
              </div>
              <div class="preview-grid">
                <div
                  v-for="(item, idx) in studentList"
                  :key="idx"
                  class="preview-item"
                  :class="{ 'is-pdf': isDocType(item) }"
                  draggable="true"
                  @dragstart="onStudentDragStart(idx)"
                  @dragover.prevent="onStudentDragOver(idx)"
                  @drop.prevent="onStudentDropReorder(idx)"
                  @dragend="studentDragIdx = null"
                >
                  <img v-if="item.preview" :src="item.preview" @error="e => e.target.style.display='none'" />
                  <div v-else class="doc-icon">&#x1F4C4;</div>
                  <div class="preview-label">{{ item.name }}</div>
                  <div class="preview-size">{{ formatSize(item.file?.size || 0) }}</div>
                  <button class="preview-remove" @click.stop="removeStudent(idx)">&#x2715;</button>
                  <div v-if="idx === studentDragOverIdx && studentDragIdx !== idx" class="drop-indicator"></div>
                </div>
              </div>
            </div>
          </template>

          <!-- Error display -->
          <div v-if="uploadError" style="margin-top:8px;padding:8px 12px;background:#FEF2F2;border:1px solid #FCA5A5;border-radius:8px;color:#B91C1C;font-size:12px">{{ uploadError }}</div>

          <!-- Submit button -->
          <button
            class="btn btn-primary btn-block"
            style="margin-top:10px"
            @click="submitUpload"
            :disabled="!canSubmit || uploading"
          >
            <span v-if="uploading">{{ uploadProgress }}% 上传中...</span>
            <span v-else>&#x1F4E4; 提交AI批改</span>
          </button>
          <div v-if="!canSubmit && !uploading" style="font-size:11px;color:var(--gray-400);text-align:center;margin-top:4px">
            需要上传至少1份答案和1份学生试卷
          </div>
        </div>

        <!-- No answer uploaded yet, hint to upload -->
        <div v-if="answerFileCount === 0" style="text-align:center;padding:12px;color:var(--gray-400);font-size:12px">
          &#x2B06;&#xFE0F; 请先上传标准答案
        </div>
      </div>

      <!-- Step 3: AI Processing -->
      <div v-if="step === 3" style="text-align:center;padding:40px 20px">
        <div style="font-size:56px">&#x23F3;</div>
        <h3 style="margin-top:12px">AI批改处理中</h3>
        <div style="display:flex;align-items:center;justify-content:center;gap:6px;margin-top:8px">
          <span style="font-size:13px;color:var(--gray-500)">正在识别手写内容并匹配知识点</span>
          <span class="pulse" style="width:6px;height:6px;border-radius:50%;background:var(--primary);display:inline-block"></span>
        </div>
        <div style="margin-top:16px;background:var(--gray-100);border-radius:6px;height:6px;overflow:hidden">
          <div :style="{ height: '100%', background: 'var(--primary)', borderRadius: '6px', width: aiProgress + '%' }"></div>
        </div>
        <p style="font-size:12px;color:var(--gray-400);margin-top:6px">预计约20秒，请稍候...</p>
        <button class="btn btn-primary" style="margin-top:20px" @click="goGrading" :disabled="aiProgress < 100">
          {{ aiProgress >= 100 ? '查看诊断结果 →' : '处理中...' }}
        </button>
      </div>
    </div>

    <BottomNav :items="teacherNav" active="upload" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { tasksAPI } from '@/api/tasks'
import { studentsAPI } from '@/api/students'
import request from '@/api/request'
import BottomNav from '@/components/BottomNav.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import EmptyState from '@/components/EmptyState.vue'
import { icons } from '@/utils/icons'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()

// ── State ─────────────────────────────────────────────
const loading = ref(true)
const step = ref(1)
const selTask = ref(null)
const selStudentId = ref('')
const aiProgress = ref(0)
const allTasks = ref([])
const allStudents = ref([])
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadError = ref('')

// Drag & drop state
const answerDragOver = ref(false)
const studentDragOver = ref(false)
const answerDragIdx = ref(null)
const studentDragIdx = ref(null)
const answerDragOverIdx = ref(null)
const studentDragOverIdx = ref(null)

// File lists: { name, file, preview, page }
const answerList = ref([])
const studentList = ref([])

// Input refs
const ansInput = ref(null)
const stuInput = ref(null)

let progressInterval = null

const MAX_FILE_SIZE = 50 * 1024 * 1024  // 50MB
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp',
  'application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
const ALLOWED_EXTS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.pdf', '.doc', '.docx']

// ── Computed ──────────────────────────────────────────
const user = computed(() => authStore.user)

const pendingTasks = computed(() => {
  if (!allTasks.value.length) return []
  const userClasses = (user.value?.classes || []).map(c => Number(c))
  const pending = allTasks.value.filter(t => {
    if (!['draft', 'pending_upload'].includes(t.status)) return false
    const taskClassIds = (t.classIds || t.class_ids || []).map(id => Number(id))
    if (!userClasses.length) return true
    return userClasses.some(c => taskClassIds.includes(c))
  })
  return pending.length ? pending : allTasks.value.filter(t => ['draft', 'pending_upload'].includes(t.status)).slice(0, 5)
})

const taskStudents = computed(() => {
  if (!selTask.value) return []
  const taskClassIds = (selTask.value.classIds || selTask.value.class_ids || []).map(id => Number(id))
  const userClasses = (user.value?.classes || []).map(c => Number(c))
  return allStudents.value.filter(s => {
    const sid = Number(s.class_id || s.classId || 0)
    // Student must be in task's class AND in teacher's class scope
    const inTaskClass = taskClassIds.includes(sid)
    const inTeacherScope = !userClasses.length || userClasses.includes(sid)
    return inTaskClass && inTeacherScope
  })
})

const pageCount = computed(() => Number(selTask.value?.pages || 4))
const answerFileCount = computed(() => answerList.value.length)
const studentFileCount = computed(() => studentList.value.length)
const canSubmit = computed(() => answerFileCount.value > 0 && studentFileCount.value > 0 && selStudentId.value && !uploading.value)

const teacherNav = [
  { key: 'students', label: '学生', icon: icons.students },
  { key: 'tasks', label: '任务', icon: icons.tasks },
  { key: 'upload', label: '上传', icon: icons.upload },
  { key: 'exercise', label: '练习', icon: icons.exercise },
  { key: 'me', label: '我的', icon: icons.home },
]

function onNav(key) {
  const map = { students: '/teacher/students', tasks: '/teacher/tasks', exercise: '/teacher/exercise', me: '/teacher/me' }
  if (map[key]) router.push(map[key])
}

// ── Helpers ───────────────────────────────────────────
function formatSize(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function isDocType(item) {
  const name = (item.name || '').toLowerCase()
  return name.endsWith('.pdf') || name.endsWith('.doc') || name.endsWith('.docx')
}

function validateFile(file) {
  if (!file) return '无效文件'
  const ext = '.' + (file.name || '').split('.').pop().toLowerCase()
  if (!ALLOWED_EXTS.includes(ext) && !ALLOWED_TYPES.includes(file.type)) {
    return '不支持的文件格式，支持: JPG/PNG/PDF/Word'
  }
  if (file.size > MAX_FILE_SIZE) {
    return '文件 "' + file.name + '" 超过50MB限制'
  }
  return null
}

// ── File Input Triggers ───────────────────────────────
function triggerAnswerInput() { ansInput.value?.click() }
function triggerStudentInput() { stuInput.value?.click() }

function onAnswerFilesSelected(e) {
  addFiles(Array.from(e.target.files || []), answerList, true)
  e.target.value = ''
}
function onStudentFilesSelected(e) {
  addFiles(Array.from(e.target.files || []), studentList, false)
  e.target.value = ''
}

// ── Add files with validation and preview ─────────────
function addFiles(files, list, isAnswer) {
  let errorShown = false
  files.forEach(file => {
    const err = validateFile(file)
    if (err) {
      if (!errorShown) { appStore.showToast(err); errorShown = true }
      return
    }
    const preview = file.type.startsWith('image/') ? URL.createObjectURL(file) : null
    list.value.push({ name: file.name, file, preview, page: list.value.length + 1 })
    // Auto-upload to backend
    uploadFileToServer(file, list.value.length, isAnswer)
  })
}

// ── Drag & Drop ──────────────────────────────────────
function onAnswerDrop(e) {
  answerDragOver.value = false
  addFiles(Array.from(e.dataTransfer.files || []), answerList, true)
}
function onStudentDrop(e) {
  studentDragOver.value = false
  addFiles(Array.from(e.dataTransfer.files || []), studentList, false)
}

// Answer reorder
function onAnswerDragStart(idx) { answerDragIdx.value = idx }
function onAnswerDragOver(idx) { answerDragOverIdx.value = idx }
function onAnswerDropReorder(toIdx) {
  if (answerDragIdx.value === null || answerDragIdx.value === toIdx) return
  const list = answerList.value
  const [item] = list.splice(answerDragIdx.value, 1)
  list.splice(toIdx, 0, item)
  answerDragIdx.value = null; answerDragOverIdx.value = null
}

// Student reorder
function onStudentDragStart(idx) { studentDragIdx.value = idx }
function onStudentDragOver(idx) { studentDragOverIdx.value = idx }
function onStudentDropReorder(toIdx) {
  if (studentDragIdx.value === null || studentDragIdx.value === toIdx) return
  const list = studentList.value
  const [item] = list.splice(studentDragIdx.value, 1)
  list.splice(toIdx, 0, item)
  studentDragIdx.value = null; studentDragOverIdx.value = null
}

// ── Remove files ─────────────────────────────────────
function removeAnswer(idx) {
  const item = answerList.value[idx]
  if (item?.preview) URL.revokeObjectURL(item.preview)
  answerList.value.splice(idx, 1)
}
function removeStudent(idx) {
  const item = studentList.value[idx]
  if (item?.preview) URL.revokeObjectURL(item.preview)
  studentList.value.splice(idx, 1)
}
function clearAnswerFiles() {
  answerList.value.forEach(item => { if (item.preview) URL.revokeObjectURL(item.preview) })
  answerList.value = []
}
function clearStudentFiles() {
  studentList.value.forEach(item => { if (item.preview) URL.revokeObjectURL(item.preview) })
  studentList.value = []
}

function onStudentChange() {
  clearStudentFiles()
}

// ── Upload single file to server ──────────────────────
async function uploadFileToServer(file, pageNum, isAnswer) {
  const taskId = selTask.value?.id
  if (!taskId) return
  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('student_id', selStudentId.value || 0)
    formData.append('page_number', pageNum)
    formData.append('is_answer_key', isAnswer)

    await request.post(`/upload/${taskId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  } catch (e) {
    console.error('Upload failed:', e)
    // Silently fail - the file is already in the preview list
  }
}

// ── Lifecycle ─────────────────────────────────────────
async function loadData() {
  loading.value = true
  try {
    const [taskRes, stuRes] = await Promise.allSettled([
      tasksAPI.getList(),
      studentsAPI.getList(),
    ])
    if (taskRes.status === 'fulfilled') {
      const r = taskRes.value; allTasks.value = r?.items || r?.data || r || []
    }
    if (stuRes.status === 'fulfilled') {
      const r = stuRes.value; allStudents.value = r?.items || r?.data || r || []
    }
  } catch {
    // Keep empty arrays
  } finally {
    loading.value = false
  }
  // Check for taskId in query
  const taskId = router.currentRoute.value.query.taskId
  if (taskId) {
    await nextTick()
    const found = allTasks.value.find(t => String(t.id) === String(taskId))
    if (found) selectTask(found)
  }
}

async function selectTask(t) {
  selTask.value = t
  step.value = 2
  clearAnswerFiles()
  clearStudentFiles()
  selStudentId.value = ''
  uploadError.value = ''
}

// ── Submit for AI grading ─────────────────────────────
async function submitUpload() {
  uploadError.value = ''

  if (answerFileCount.value === 0) {
    uploadError.value = '请先上传至少1份标准答案'
    return
  }
  if (!selStudentId.value) {
    uploadError.value = '请选择学生'
    return
  }
  if (studentFileCount.value === 0) {
    uploadError.value = '请上传至少1份学生试卷'
    return
  }

  uploading.value = true
  uploadProgress.value = 100
  uploading.value = false

  // Enter AI processing
  if (selTask.value) selTask.value.status = 'ai_processing'
  step.value = 3
  aiProgress.value = 10
  if (progressInterval) clearInterval(progressInterval)
  progressInterval = setInterval(() => {
    aiProgress.value += 15
    if (aiProgress.value >= 100) {
      aiProgress.value = 100
      clearInterval(progressInterval)
      progressInterval = null
    }
  }, 800)

  const taskId = selTask.value?.id
  if (taskId) {
    tasksAPI.runAI(taskId).catch(() => {})
  }
}

function goGrading() {
  if (progressInterval) clearInterval(progressInterval)
  const taskId = selTask.value?.id || 1
  router.push('/teacher/grading/' + taskId)
}

onMounted(loadData)

onBeforeUnmount(() => {
  if (progressInterval) clearInterval(progressInterval)
  answerList.value.forEach(item => { if (item.preview) URL.revokeObjectURL(item.preview) })
  studentList.value.forEach(item => { if (item.preview) URL.revokeObjectURL(item.preview) })
})
</script>

<style scoped>
.drop-zone {
  border: 2px dashed var(--gray-300);
  border-radius: 10px;
  padding: 24px 16px;
  text-align: center;
  cursor: pointer;
  transition: all .2s;
  background: var(--gray-50);
}
.drop-zone:hover, .drop-zone.drop-active {
  border-color: var(--primary);
  background: var(--primary-light);
}
.preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 8px;
}
.preview-item {
  position: relative;
  aspect-ratio: 3/4;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid var(--gray-200);
  cursor: grab;
  transition: border-color .2s;
  background: var(--gray-50);
}
.preview-item:active { cursor: grabbing; }
.preview-item img {
  width: 100%; height: 100%; object-fit: cover;
}
.preview-item .doc-icon {
  width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  font-size: 36px; color: var(--gray-400);
  background: linear-gradient(135deg, #f0f4ff, #e8ecf4);
}
.preview-item.is-pdf { border-color: #7c3aed; }
.preview-label {
  position: absolute; bottom: 20px; left: 0; right: 0;
  background: rgba(0,0,0,.6); color: #fff;
  font-size: 9px; padding: 2px 4px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.preview-size {
  position: absolute; bottom: 4px; right: 4px;
  font-size: 8px; color: rgba(255,255,255,.7);
  background: rgba(0,0,0,.5); padding: 1px 4px; border-radius: 3px;
}
.preview-remove {
  position: absolute; top: 2px; right: 2px;
  width: 18px; height: 18px; border-radius: 50%;
  background: rgba(0,0,0,.7); color: #fff;
  border: none; font-size: 10px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  z-index: 2;
}
.drop-indicator {
  position: absolute; top: 0; bottom: 0; left: -3px; width: 3px;
  background: var(--primary); z-index: 3;
}
.pulse {
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: .3; }
}
.fade-in {
  animation: fadeIn .3s ease;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
