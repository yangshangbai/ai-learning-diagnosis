<template>
  <div class="page">
    <PageHeader title="题目资料库">
      <template #actions>
        <button class="btn btn-sm btn-outline" @click="router.push('/admin/question-sources')">题源架构</button>
        <button class="btn btn-sm btn-primary" @click="handleAdd">+ 添加题目</button>
      </template>
    </PageHeader>
    <div class="page-body">
      <!-- Service Status -->
      <div class="card" style="background:#F0FDFA;border-color:#99F6E4">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:8px">
          <div>
            <div style="font-weight:600;font-size:14px">统一题库服务</div>
            <div style="font-size:12px;color:var(--gray-500);margin-top:3px">教研云 + 本地题库 · 最近调度 {{ lastSync }}</div>
          </div>
          <span class="tag tag-green">运行正常</span>
        </div>
        <div style="font-size:11px;color:var(--gray-500);margin-top:8px">老师出题时由系统自动路由，题目搬运、映射和质量治理由管理员维护。</div>
      </div>

      <!-- Filters -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:10px">
        <select class="input select" v-model="sourceFilter" style="height:34px;font-size:12px">
          <option value="">全部题源</option>
          <option v-for="s in SOURCE_TYPES" :value="s" :key="s">{{ s }}</option>
        </select>
        <select class="input select" v-model="subjectFilter" style="height:34px;font-size:12px">
          <option value="">全部学科</option>
          <option v-for="s in SUBJECTS" :value="s" :key="s">{{ s }}</option>
        </select>
      </div>

      <!-- Counts & Basket -->
      <div style="font-size:12px;color:var(--gray-500);margin-bottom:8px;display:flex;justify-content:space-between;align-items:center">
        <span>共{{ filteredQuestions.length }}道 · 练习篮{{ basketCount }}道</span>
        <button v-if="basketCount > 0" class="btn btn-sm btn-outline" style="color:var(--danger);border-color:var(--danger)" @click="clearBasket">清空练习篮</button>
      </div>

      <!-- Question Cards -->
      <div v-if="filteredQuestions.length === 0" style="text-align:center;color:var(--gray-400);padding:40px 20px">暂无题目</div>
      <div v-for="q in filteredQuestions" :key="q.id" class="card" style="margin-bottom:8px">
        <div style="font-weight:500;font-size:13px;line-height:1.5">{{ q.title || q.content }}</div>
        <div style="display:flex;gap:5px;margin-top:6px;flex-wrap:wrap">
          <span class="tag" :class="q.source === '教研云' ? 'tag-green' : 'tag-primary'">{{ q.source || '本地题库' }}</span>
          <span class="tag tag-gray">{{ q.type || '选择题' }}</span>
          <span class="tag tag-gray">{{ difficultyStarsText(q.difficulty || 2) }}</span>
          <span class="tag tag-gray">{{ q.kp || q.knowledge_point || q.knowledgePoint || '' }}</span>
          <span style="font-size:11px;color:var(--gray-400)">{{ q.subject || '' }} · {{ q.grade || '' }}</span>
        </div>
        <div v-if="q.externalId || q.external_id" style="font-size:10px;color:var(--gray-400);margin-top:5px">
          外部题号 {{ q.externalId || q.external_id }} · {{ q.syncStatus || q.sync_status || '已同步' }}
        </div>
        <div style="margin-top:8px;display:flex;gap:5px">
          <button class="btn btn-sm btn-outline" @click="handlePreview(q)">预览</button>
          <button class="btn btn-sm btn-outline" @click="addToBasket(q)" :disabled="basketIds.includes(q.id)">
            {{ basketIds.includes(q.id) ? '已加入' : '加入练习篮' }}
          </button>
          <button class="btn btn-sm btn-outline" @click="handleEdit(q)">编辑标签</button>
          <button class="btn btn-sm btn-outline" style="color:var(--danger)" @click="handleDelete(q)">删除</button>
        </div>
      </div>
    </div>

    <!-- Create/Edit Modal -->
    <CrudModal :show="showModal" :title="editingQuestion ? '编辑题目' : '添加题目'" @close="closeModal" @save="handleSave">
      <div class="input-group">
        <label>题目内容 <span style="color:var(--danger)">*</span></label>
        <textarea class="input textarea" v-model="form.content" placeholder="请输入题目内容"></textarea>
        <div v-if="formErrors.content" style="font-size:11px;color:var(--danger);margin-top:2px">{{ formErrors.content }}</div>
      </div>
      <div class="input-group">
        <label>题型 <span style="color:var(--danger)">*</span></label>
        <select class="input select" v-model="form.type">
          <option value="">请选择题型</option>
          <option v-for="t in QUESTION_TYPES" :value="t" :key="t">{{ t }}</option>
        </select>
        <div v-if="formErrors.type" style="font-size:11px;color:var(--danger);margin-top:2px">{{ formErrors.type }}</div>
      </div>
      <div class="input-group">
        <label>学科 <span style="color:var(--danger)">*</span></label>
        <select class="input select" v-model="form.subject">
          <option value="">请选择学科</option>
          <option v-for="s in SUBJECTS" :value="s" :key="s">{{ s }}</option>
        </select>
        <div v-if="formErrors.subject" style="font-size:11px;color:var(--danger);margin-top:2px">{{ formErrors.subject }}</div>
      </div>
      <div class="input-group">
        <label>年级</label>
        <select class="input select" v-model="form.grade">
          <option value="">请选择年级</option>
          <option v-for="g in refStore.gradeNames" :value="g" :key="g">{{ g }}</option>
        </select>
      </div>
      <div class="input-group">
        <label>难度</label>
        <select class="input select" v-model.number="form.difficulty">
          <option :value="1">基础</option>
          <option :value="2">中等</option>
          <option :value="3">拔高</option>
        </select>
      </div>
      <div class="input-group">
        <label>知识点</label>
        <select class="input select" v-model="form.knowledge_point_id">
          <option value="">请选择知识点</option>
          <option v-for="kp in knowledgeNodes" :key="kp.id" :value="kp.id">{{ kp.name }}</option>
        </select>
      </div>
      <div class="input-group">
        <label>题源</label>
        <select class="input select" v-model="form.source">
          <option v-for="s in SOURCE_TYPES" :value="s" :key="s">{{ s }}</option>
        </select>
      </div>
      <div class="input-group">
        <label>外部ID <span style="font-size:11px;color:var(--gray-400)">(教研云题源时填写)</span></label>
        <input class="input" v-model="form.external_id" placeholder="可选" />
      </div>
      <!-- Delete button when editing -->
      <div v-if="editingQuestion" style="margin-top:8px;padding-top:12px;border-top:1px solid var(--gray-200)">
        <button class="btn btn-sm btn-danger btn-block" @click="handleDelete(editingQuestion)">删除此题</button>
      </div>
    </CrudModal>

    <!-- Preview Modal -->
    <teleport to="body">
      <div v-if="showPreview" class="overlay" @click.self="showPreview = false">
        <div class="qb-sheet">
          <div class="qb-sheet-handle"></div>
          <h3 class="qb-sheet-title">题目详情</h3>
          <div class="qb-sheet-body">
            <div v-if="previewQuestion" style="font-size:14px;line-height:1.6">
              <div style="font-weight:600;margin-bottom:12px;color:var(--gray-900)">{{ previewQuestion.title || previewQuestion.content }}</div>
              <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px">
                <span class="tag" :class="previewQuestion.source === '教研云' ? 'tag-green' : 'tag-primary'">{{ previewQuestion.source || '本地题库' }}</span>
                <span class="tag tag-gray">{{ previewQuestion.type || '-' }}</span>
                <span class="tag tag-gray">{{ difficultyStarsText(previewQuestion.difficulty || 2) }}</span>
              </div>
              <div style="font-size:12px;color:var(--gray-500);margin-bottom:4px">
                <div>学科：{{ previewQuestion.subject || '-' }}</div>
                <div>年级：{{ previewQuestion.grade || '-' }}</div>
                <div>知识点：{{ previewQuestion.kp || previewQuestion.knowledge_point || previewQuestion.knowledgePoint || '-' }}</div>
                <div v-if="previewQuestion.externalId || previewQuestion.external_id">
                  外部题号：{{ previewQuestion.externalId || previewQuestion.external_id }}
                </div>
                <div v-if="previewQuestion.syncStatus || previewQuestion.sync_status">
                  同步状态：{{ previewQuestion.syncStatus || previewQuestion.sync_status }}
                </div>
              </div>
            </div>
          </div>
          <div class="qb-sheet-footer">
            <button class="btn btn-primary btn-block" @click="showPreview = false">关闭</button>
          </div>
        </div>
      </div>
    </teleport>

    <BottomNav :items="navItems" active="qbank" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import BottomNav from '@/components/BottomNav.vue'
import CrudModal from '@/components/CrudModal.vue'
import { questionsAPI } from '@/api/questions'
import { knowledgeAPI } from '@/api/knowledge'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { icons } from '@/utils/icons'
import { difficultyStars } from '@/utils/helpers'
import { SUBJECTS, QUESTION_TYPES, SOURCE_TYPES, DIFFICULTY_LEVELS } from '@/utils/constants'
import { useReferenceStore } from '@/stores/reference'

const router = useRouter()
const authStore = useAuthStore()
const refStore = useReferenceStore()
const appStore = useAppStore()

const user = computed(() => authStore.user || JSON.parse(localStorage.getItem('user') || 'null'))
const role = computed(() => user.value?.role || 'research')

const sourceFilter = ref('')
const subjectFilter = ref('')
const questions = ref([])
const lastSync = ref('今天16:20')
const knowledgeNodes = ref([])

// Basket
const basketIds = ref([])
const basketCount = computed(() => basketIds.value.length)

// Modal state
const showModal = ref(false)
const editingQuestion = ref(null)
const saving = ref(false)

// Preview state
const showPreview = ref(false)
const previewQuestion = ref(null)

const form = ref({
  content: '',
  type: '',
  subject: '',
  grade: '',
  difficulty: 2,
  knowledge_point_id: '',
  source: '本地题库',
  external_id: ''
})

const formErrors = ref({})

const defaultForm = () => ({
  content: '',
  type: '',
  subject: '',
  grade: '',
  difficulty: 2,
  knowledge_point_id: '',
  source: '本地题库',
  external_id: ''
})

const researchNav = [
  { key: 'knowledge', label: '知识库', icon: icons.knowledge },
  { key: 'qbank', label: '题库', icon: icons.qbank },
  { key: 'ai', label: 'AI', icon: icons.ai },
  { key: 'diagnosis', label: '诊断', icon: icons.diagnosis },
  { key: 'me', label: '我的', icon: icons.home },
]

const superNav = [
  { key: 'dashboard', label: '总览', icon: icons.dashboard },
  { key: 'knowledge', label: '知识库', icon: icons.knowledge },
  { key: 'qbank', label: '题库', icon: icons.qbank },
  { key: 'ai', label: 'AI', icon: icons.ai },
  { key: 'system', label: '系统', icon: icons.settings },
  { key: 'diagnosis', label: '诊断', icon: icons.diagnosis },
  { key: 'me', label: '我的', icon: icons.home },
]

const navItems = computed(() => role.value === 'super' ? superNav : researchNav)

const filteredQuestions = computed(() => {
  return questions.value.filter(q => {
    const sourceMatch = !sourceFilter.value || q.source === sourceFilter.value
    const subjectMatch = !subjectFilter.value || q.subject === subjectFilter.value
    return sourceMatch && subjectMatch
  })
})

function showToast(msg) {
  appStore.showToast(msg)
}

function difficultyStarsText(n) {
  return difficultyStars(n)
}

function flattenKnowledgeTree(nodes, result = []) {
  for (const node of nodes) {
    result.push({ id: node.id, name: node.name || node.label })
    if (node.children && node.children.length) {
      flattenKnowledgeTree(node.children, result)
    }
  }
  return result
}

// CRUD handlers
function handleAdd() {
  editingQuestion.value = null
  form.value = defaultForm()
  formErrors.value = {}
  showModal.value = true
}

function handleEdit(q) {
  editingQuestion.value = q
  form.value = {
    content: q.title || q.content || '',
    type: q.type || '',
    subject: q.subject || '',
    grade: q.grade || '',
    difficulty: q.difficulty || 2,
    knowledge_point_id: q.knowledge_point_id || q.knowledgePointId || '',
    source: q.source || '本地题库',
    external_id: q.externalId || q.external_id || ''
  }
  formErrors.value = {}
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  editingQuestion.value = null
}

function validateForm() {
  const errors = {}
  if (!form.value.content.trim()) errors.content = '请输入题目内容'
  if (!form.value.type) errors.type = '请选择题型'
  if (!form.value.subject) errors.subject = '请选择学科'
  formErrors.value = errors
  return Object.keys(errors).length === 0
}

async function handleSave() {
  if (!validateForm()) return
  if (saving.value) return
  saving.value = true

  const payload = {
    content: form.value.content.trim(),
    type: form.value.type,
    subject: form.value.subject,
    grade: form.value.grade || null,
    difficulty: form.value.difficulty,
    knowledge_point_id: form.value.knowledge_point_id || null,
    source: form.value.source,
    external_id: form.value.external_id || null
  }

  try {
    if (editingQuestion.value) {
      await questionsAPI.update(editingQuestion.value.id, payload)
      showToast('题目已更新')
    } else {
      await questionsAPI.create(payload)
      showToast('题目已添加')
    }
    closeModal()
    await fetchQuestions()
  } catch (e) {
    showToast('操作失败')
    console.warn('Save question failed:', e)
  } finally {
    saving.value = false
  }
}

async function handleDelete(q) {
  if (!confirm('确认删除该题目?')) return
  try {
    await questionsAPI.remove(q.id)
    showToast('已删除')
    closeModal()
    await fetchQuestions()
  } catch (e) {
    showToast('删除失败')
    console.warn('Delete question failed:', e)
  }
}

// Preview
function handlePreview(q) {
  previewQuestion.value = q
  showPreview.value = true
}

// Basket
function addToBasket(q) {
  if (!basketIds.value.includes(q.id)) {
    basketIds.value.push(q.id)
    showToast('已加入练习篮')
  }
}

function clearBasket() {
  basketIds.value = []
  showToast('练习篮已清空')
}

function onNav(key) {
  const map = {
    dashboard: '/admin/dashboard',
    knowledge: '/admin/knowledge',
    qbank: '/admin/qbank',
    ai: '/admin/ai',
    diagnosis: '/admin/diagnosis',
    system: '/admin/system',
    me: '/admin/me'
  }
  if (map[key]) router.push(map[key])
}

async function fetchQuestions() {
  try {
    const res = await questionsAPI.getList()
    questions.value = res?.items || res?.data || (Array.isArray(res) ? res : [])
  } catch (e) {
    console.warn('Failed to fetch questions:', e)
  }
}

async function fetchKnowledgeFlat() {
  try {
    const res = await knowledgeAPI.getTree()
    const data = res?.items || res?.data || (Array.isArray(res) ? res : [])
    knowledgeNodes.value = flattenKnowledgeTree(data)
  } catch (e) {
    console.warn('Failed to fetch knowledge nodes:', e)
  }
}

onMounted(async () => {
  await refStore.fetchAll()
  fetchQuestions()
  fetchKnowledgeFlat()
})
</script>

<style scoped>
.input {
  width: 100%;
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-sm);
  font-size: 14px;
  box-sizing: border-box;
}
.select {
  appearance: auto;
  padding: 0 8px;
}

/* Preview bottom sheet (same pattern as CrudModal) */
.qb-sheet {
  background: #fff;
  border-radius: var(--radius) var(--radius) 0 0;
  width: 100%;
  max-width: 420px;
  margin: 0 auto;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  animation: qbSlideUp .3s ease;
}
@keyframes qbSlideUp {
  from { transform: translateY(100%) }
  to { transform: translateY(0) }
}
.qb-sheet-handle {
  width: 36px;
  height: 4px;
  background: var(--gray-300);
  border-radius: 2px;
  margin: 12px auto 8px;
}
.qb-sheet-title {
  font-size: 16px;
  font-weight: 600;
  text-align: center;
  padding: 0 16px 12px;
}
.qb-sheet-body {
  flex: 1;
  overflow-y: auto;
  padding: 0 16px;
}
.qb-sheet-footer {
  display: flex;
  gap: 12px;
  padding: 16px;
  border-top: 1px solid var(--gray-200);
}
.qb-sheet-footer .btn {
  flex: 1;
}
</style>
