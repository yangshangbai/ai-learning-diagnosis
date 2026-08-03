<template>
  <div class="page">
    <PageHeader title="知识点体系">
      <template #actions>
        <button class="btn btn-sm btn-primary" @click="handleAdd" v-html="icons.plus" style="width:32px;height:32px;padding:0"></button>
        <button class="btn btn-sm btn-outline" @click="handleAiSuggest" :disabled="aiLoading">
          {{ aiLoading ? '分析中...' : 'AI建议' }}
        </button>
      </template>
    </PageHeader>
    <div class="page-body">
      <!-- AI Suggestion Result -->
      <div v-if="aiResult" class="card" style="background:var(--primary-light);border-color:var(--primary)">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <div style="font-weight:600;font-size:14px;color:var(--primary)">AI 建议</div>
          <button class="btn-ghost" style="font-size:12px;padding:2px 6px" @click="aiResult = null">&times;</button>
        </div>
        <div v-if="aiResult.suggestions && aiResult.suggestions.length" style="font-size:12px;color:var(--gray-700);line-height:1.6">
          <div v-for="(s, i) in aiResult.suggestions" :key="i" style="margin-bottom:6px">
            <strong>{{ i + 1 }}. {{ s.name || s.label || s }}</strong>
            <span v-if="s.reason" style="color:var(--gray-500)"> - {{ s.reason }}</span>
          </div>
        </div>
        <div v-else style="font-size:12px;color:var(--gray-500)">
          {{ typeof aiResult === 'string' ? aiResult : '暂无建议' }}
        </div>
      </div>

      <!-- Hint Card -->
      <div class="card" style="background:var(--warning-light);border-color:var(--warning)">
        <div style="font-size:12px;font-weight:600;color:var(--warning)">{{ '3个新知识点建议添加' }}</div>
      </div>

      <!-- Tree -->
      <div v-if="tree.length === 0" style="text-align:center;color:var(--gray-400);padding:40px 20px">暂无知识体系数据</div>
      <div v-for="root in tree" :key="root.id || root.name">
        <TreeNode :node="root" :depth="0" @edit="handleEdit" />
      </div>
    </div>

    <!-- Create/Edit Modal -->
    <CrudModal :show="showModal" :title="editingNode ? '编辑知识点' : '新增知识点'" @close="closeModal" @save="handleSave">
      <div class="input-group">
        <label>知识点名称 <span style="color:var(--danger)">*</span></label>
        <input class="input" v-model="form.name" placeholder="请输入知识点名称" />
        <div v-if="formErrors.name" style="font-size:11px;color:var(--danger);margin-top:2px">{{ formErrors.name }}</div>
      </div>
      <div class="input-group">
        <label>父节点</label>
        <select class="input select" v-model="form.parent_id">
          <option :value="null">无 (根节点)</option>
          <option v-for="n in flatNodes" :key="n.id" :value="n.id" :disabled="n.id === editingNode?.id">{{ n.name }}</option>
        </select>
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
        <label>学段</label>
        <select class="input select" v-model="form.stage">
          <option value="">请选择学段</option>
          <option v-for="s in STAGES" :value="s" :key="s">{{ s }}</option>
        </select>
      </div>
      <div class="input-group">
        <label>层级</label>
        <select class="input select" v-model.number="form.level">
          <option :value="0">0 - 学科根</option>
          <option :value="1">1 - 模块</option>
          <option :value="2">2 - 单元</option>
          <option :value="3">3 - 小节</option>
          <option :value="4">4 - 知识点</option>
        </select>
      </div>
      <div class="input-group">
        <label>关键词</label>
        <input class="input" v-model="form.keywordsInput" placeholder="逗号分隔，如：加法,交换律" />
      </div>
      <div class="input-group">
        <label>排序</label>
        <input class="input" type="number" v-model.number="form.sort_order" placeholder="数字越小越靠前" />
      </div>
      <div class="input-group">
        <label>掌握度 (0-100)</label>
        <input class="input" type="number" min="0" max="100" v-model.number="form.mastery" placeholder="可选" />
      </div>
      <!-- Delete button when editing -->
      <div v-if="editingNode" style="margin-top:8px;padding-top:12px;border-top:1px solid var(--gray-200)">
        <button class="btn btn-sm btn-danger btn-block" @click="handleDelete">删除此节点</button>
      </div>
    </CrudModal>

    <BottomNav :items="navItems" active="knowledge" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import BottomNav from '@/components/BottomNav.vue'
import TreeNode from '@/components/TreeNode.vue'
import CrudModal from '@/components/CrudModal.vue'
import { knowledgeAPI } from '@/api/knowledge'
import { aiAPI } from '@/api/ai'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { icons } from '@/utils/icons'
import { SUBJECTS, STAGES } from '@/utils/constants'
import { useReferenceStore } from '@/stores/reference'

const router = useRouter()
const authStore = useAuthStore()
const refStore = useReferenceStore()
const appStore = useAppStore()

const user = computed(() => authStore.user || JSON.parse(localStorage.getItem('user') || 'null'))
const role = computed(() => user.value?.role || 'research')

const tree = ref([])
const flatNodes = ref([])
const showModal = ref(false)
const editingNode = ref(null)
const aiLoading = ref(false)
const aiResult = ref(null)
const saving = ref(false)

const form = ref({
  name: '',
  parent_id: null,
  subject: '',
  grade: '',
  stage: '',
  level: 0,
  keywordsInput: '',
  sort_order: 0,
  mastery: null
})

const formErrors = ref({})

const defaultForm = () => ({
  name: '',
  parent_id: null,
  subject: '',
  grade: '',
  stage: '',
  level: 0,
  keywordsInput: '',
  sort_order: 0,
  mastery: null
})

function resetForm() {
  form.value = defaultForm()
  formErrors.value = {}
}

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

function showToast(msg) {
  appStore.showToast(msg)
}

function flattenTree(nodes, result = []) {
  for (const node of nodes) {
    result.push({ id: node.id, name: node.name || node.label })
    if (node.children && node.children.length) {
      flattenTree(node.children, result)
    }
  }
  return result
}

function handleAdd() {
  editingNode.value = null
  resetForm()
  showModal.value = true
}

function handleEdit(node) {
  editingNode.value = node
  form.value = {
    name: node.name || node.label || '',
    parent_id: node.parent_id || node.parentId || null,
    subject: node.subject || '',
    grade: node.grade || '',
    stage: node.stage || '',
    level: node.level ?? 0,
    keywordsInput: Array.isArray(node.keywords) ? node.keywords.join(',') : (node.keywords || ''),
    sort_order: node.sort_order || node.sortOrder || 0,
    mastery: node.mastery ?? null
  }
  formErrors.value = {}
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  editingNode.value = null
  resetForm()
}

function validateForm() {
  const errors = {}
  if (!form.value.name.trim()) errors.name = '请输入知识点名称'
  if (!form.value.subject) errors.subject = '请选择学科'
  formErrors.value = errors
  return Object.keys(errors).length === 0
}

async function handleSave() {
  if (!validateForm()) return
  if (saving.value) return
  saving.value = true

  const payload = {
    name: form.value.name.trim(),
    parent_id: form.value.parent_id || null,
    subject: form.value.subject,
    grade: form.value.grade || null,
    stage: form.value.stage || null,
    level: form.value.level,
    keywords: form.value.keywordsInput
      ? form.value.keywordsInput.split(',').map(s => s.trim()).filter(Boolean)
      : [],
    sort_order: form.value.sort_order || 0,
    mastery: form.value.mastery
  }

  try {
    if (editingNode.value) {
      await knowledgeAPI.update(editingNode.value.id, payload)
      showToast('知识点已更新')
    } else {
      await knowledgeAPI.create(payload)
      showToast('知识点已创建')
    }
    closeModal()
    await fetchTree()
  } catch (e) {
    showToast('操作失败')
    console.warn('Save knowledge node failed:', e)
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  if (!editingNode.value) return
  if (!confirm('确认删除知识点: ' + (editingNode.value.name || editingNode.value.label) + '? 其子节点也将被删除。')) return
  try {
    await knowledgeAPI.remove(editingNode.value.id)
    showToast('已删除')
    closeModal()
    await fetchTree()
  } catch (e) {
    showToast('删除失败')
    console.warn('Delete knowledge node failed:', e)
  }
}

async function handleAiSuggest() {
  if (aiLoading.value) return
  aiLoading.value = true
  aiResult.value = null
  try {
    const res = await aiAPI.suggest({ context: 'knowledge_tree', tree: tree.value })
    aiResult.value = res && res.data !== undefined ? res.data : res
    showToast('AI建议已生成')
  } catch (e) {
    showToast('AI建议获取失败')
    console.warn('AI suggest failed:', e)
  } finally {
    aiLoading.value = false
  }
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

async function fetchTree() {
  try {
    const res = await knowledgeAPI.getTree()
    const data = res?.items || res?.data || (Array.isArray(res) ? res : [])
    if (data.length > 0) {
      tree.value = data
      flatNodes.value = flattenTree(data)
    }
  } catch (e) {
    console.warn('Failed to fetch knowledge tree:', e)
  }
}

onMounted(async () => {
  await refStore.fetchAll()
  fetchTree()
})
</script>
