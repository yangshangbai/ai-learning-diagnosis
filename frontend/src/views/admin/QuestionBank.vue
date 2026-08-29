<template>
  <div class="page">
    <PageHeader title="题目资料库">
      <template #actions>
        <button class="btn btn-sm btn-primary" @click="openGenerate">🤖 AI出题</button>
      </template>
    </PageHeader>
    <div class="page-body">
      <!-- Quick Stats -->
      <div style="display:flex;gap:8px;margin-bottom:8px;font-size:11px;color:var(--gray-500)">
        <span>共 {{ filteredQuestions.length }} 题</span>
        <span v-if="basketCount">· 练习篮 {{ basketCount }} 题</span>
        <span style="margin-left:auto">
          <button class="btn btn-sm btn-outline" style="font-size:10px" @click="exportPDF" :disabled="!filteredQuestions.length">📄 导出PDF</button>
        </span>
      </div>

      <!-- Filters — horizontal scroll mobile-first -->
      <div class="filter-bar">
        <select class="filter-select" v-model="filters.subject" @change="fetchQuestions">
          <option value="">学科</option>
          <option v-for="s in SUBJECTS" :value="s" :key="s">{{ s }}</option>
        </select>
        <select class="filter-select" v-model="filters.grade" @change="fetchQuestions">
          <option value="">年级</option>
          <option v-for="g in refStore.gradeNames" :value="g" :key="g">{{ g }}</option>
        </select>
        <select class="filter-select" v-model="filters.difficulty" @change="fetchQuestions">
          <option value="">难度</option>
          <option value="1">基础</option><option value="2">中等</option><option value="3">拔高</option>
        </select>
        <select class="filter-select" v-model="filters.category_id" @change="fetchQuestions">
          <option value="">分类</option>
          <option v-for="c in categories" :value="c.id" :key="c.id">{{ c.name }}</option>
        </select>
        <select class="filter-select" v-model="filters.source" @change="fetchQuestions">
          <option value="">来源</option>
          <option value="本地题库">本地</option><option value="AI生成">AI生成</option><option value="教研云">教研云</option>
        </select>
        <button class="btn btn-sm btn-outline" style="font-size:10px;white-space:nowrap" @click="showCategories = true">🏷️ 分类</button>
      </div>

      <!-- Question Cards -->
      <div v-if="loading" style="text-align:center;padding:20px;color:var(--gray-400)">加载中...</div>
      <template v-else>
        <div v-for="q in filteredQuestions" :key="q.id" class="q-card" @click="toggleDetail(q)">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">
            <div style="flex:1;min-width:0">
              <div style="font-size:13px;font-weight:500;line-height:1.4">{{ q.title }}</div>
              <div style="font-size:10px;color:var(--gray-400);margin-top:3px;display:flex;flex-wrap:wrap;gap:4px">
                <span class="tag tag-sm">{{ q.type }}</span>
                <span class="tag tag-sm">{{ q.grade }}·{{ q.subject }}</span>
                <span class="tag tag-sm">{{ q.kp_name }}</span>
                <span class="tag tag-sm" :style="{background: diffColor(q.difficulty)}">{{ diffLabel(q.difficulty) }}</span>
                <span v-if="q.category_name" class="tag tag-sm" style="background:#EEF2FF;color:#4F46E5">{{ q.category_name }}</span>
                <span v-if="q.source === 'AI生成'" class="tag tag-sm" style="background:#FEF3C7;color:#92400E">🤖 AI</span>
              </div>
            </div>
            <input type="checkbox" :checked="basketIds.includes(q.id)" @click.stop @change="toggleBasket(q.id)" style="flex-shrink:0" />
          </div>
          <!-- Expanded detail -->
          <div v-if="detailId === q.id" style="margin-top:8px;padding-top:8px;border-top:1px solid var(--gray-100);font-size:12px">
            <div v-if="q.answer" style="color:var(--success)">✓ 答案：{{ q.answer }}</div>
            <div v-if="q.analysis" style="color:var(--gray-500);margin-top:2px">📝 解析：{{ q.analysis }}</div>
            <div style="display:flex;gap:6px;margin-top:6px">
              <select class="filter-select" style="font-size:11px;height:28px" @click.stop @change="setCategory(q.id, $event.target.value)">
                <option value="">重分类...</option>
                <option v-for="c in categories" :value="c.id" :key="c.id" :selected="q.category_id === c.id">{{ c.name }}</option>
              </select>
              <button class="btn btn-sm btn-outline" style="font-size:10px;padding:2px 8px" @click.stop="editQuestion(q)">✏️</button>
              <button class="btn btn-sm btn-outline" style="color:var(--danger);font-size:10px;padding:2px 8px" @click.stop="deleteQuestion(q)">🗑️</button>
            </div>
          </div>
        </div>
        <div v-if="!loading && !filteredQuestions.length" style="text-align:center;color:var(--gray-400);padding:30px">
          暂无题目，点击"🤖 AI出题"生成或"添加题目"手动录入
        </div>
      </template>

      <!-- Fixed Add Bar -->
      <div class="fixed-add-bar">
        <button class="btn btn-outline btn-block" style="flex:1;margin-right:6px" @click="openGenerate">🤖 AI生成题目</button>
        <button class="btn btn-primary btn-block" style="flex:1" @click="handleAdd">+ 添加题目</button>
      </div>
    </div>

    <!-- ===== AI Generate Modal ===== -->
    <teleport to="body">
      <div v-if="showGenerate" class="overlay" @click.self="showGenerate = false">
        <div class="bottom-sheet">
          <div class="sheet-handle"></div>
          <h3 class="sheet-title">AI 生成题目</h3>
          <div class="sheet-body">
            <div class="input-group">
              <label>知识点 <span style="color:var(--danger)">*</span></label>
              <input class="input" v-model="genForm.kp_name" placeholder="如：异分母分数加减" list="kp-list" />
              <datalist id="kp-list"><option v-for="k in knowledgeKps" :value="k" :key="k" /></datalist>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
              <div class="input-group"><label>年级</label><select class="input select" v-model="genForm.grade"><option v-for="g in refStore.gradeNames" :value="g" :key="g">{{ g }}</option></select></div>
              <div class="input-group"><label>学科</label><select class="input select" v-model="genForm.subject"><option v-for="s in SUBJECTS" :value="s" :key="s">{{ s }}</option></select></div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
              <div class="input-group"><label>难度</label><select class="input select" v-model="genForm.difficulty"><option>基础</option><option>中等</option><option>拔高</option></select></div>
              <div class="input-group"><label>数量</label><input class="input" type="number" v-model.number="genForm.count" min="1" max="20" /></div>
            </div>
            <div v-if="genResult" style="margin-top:8px;background:#F0FDFA;padding:10px;border-radius:8px;font-size:12px">
              {{ genResult }}
            </div>
          </div>
          <div class="sheet-footer">
            <button class="btn btn-outline" @click="showGenerate = false">关闭</button>
            <button class="btn btn-primary" @click="doGenerate" :disabled="genLoading">{{ genLoading ? '生成中...' : '开始生成' }}</button>
          </div>
        </div>
      </div>
    </teleport>

    <!-- ===== Category Manage Modal ===== -->
    <teleport to="body">
      <div v-if="showCategories" class="overlay" @click.self="showCategories = false">
        <div class="bottom-sheet">
          <div class="sheet-handle"></div>
          <h3 class="sheet-title">题目分类管理</h3>
          <div class="sheet-body">
            <div v-for="c in categories" :key="c.id" style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
              <span :style="{width:'12px',height:'12px',borderRadius:'3px',background:c.color,flexShrink:0}"></span>
              <span style="flex:1;font-size:13px">{{ c.name }}</span>
              <button class="btn btn-sm btn-outline" style="font-size:10px;padding:2px 8px" @click="deleteCategory(c)">✕</button>
            </div>
            <div style="display:flex;gap:6px;margin-top:8px">
              <input class="input" v-model="newCatName" placeholder="新分类名" style="flex:1;font-size:13px" />
              <button class="btn btn-sm btn-primary" @click="createCategory" :disabled="!newCatName.trim()">添加</button>
            </div>
          </div>
          <div class="sheet-footer"><button class="btn btn-outline btn-block" @click="showCategories = false">关闭</button></div>
        </div>
      </div>
    </teleport>

    <!-- ===== Manual Add Modal ===== -->
    <CrudModal :show="showAdd" title="添加题目" @close="showAdd = false" @save="doAddQuestion">
      <div class="input-group">
        <label>题目内容 <span style="color:var(--danger)">*</span></label>
        <textarea class="input" v-model="addForm.title" style="min-height:60px" placeholder="题目的完整文字描述" />
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
        <div class="input-group"><label>题型</label><select class="input select" v-model="addForm.type"><option v-for="t in QUESTION_TYPES" :value="t" :key="t">{{ t }}</option></select></div>
        <div class="input-group"><label>难度</label><select class="input select" v-model.number="addForm.difficulty"><option :value="1">基础</option><option :value="2">中等</option><option :value="3">拔高</option></select></div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
        <div class="input-group"><label>年级</label><select class="input select" v-model="addForm.grade"><option v-for="g in refStore.gradeNames" :value="g" :key="g">{{ g }}</option></select></div>
        <div class="input-group"><label>学科</label><select class="input select" v-model="addForm.subject"><option v-for="s in SUBJECTS" :value="s" :key="s">{{ s }}</option></select></div>
      </div>
      <div class="input-group"><label>知识点</label><input class="input" v-model="addForm.kp_name" placeholder="如：异分母分数加减" list="kp-list2" /><datalist id="kp-list2"><option v-for="k in knowledgeKps" :value="k" :key="k" /></datalist></div>
      <div class="input-group"><label>答案</label><input class="input" v-model="addForm.answer" placeholder="标准答案" /></div>
      <div class="input-group"><label>解析</label><textarea class="input" v-model="addForm.analysis" style="min-height:40px" placeholder="解题思路（可选）" /></div>
    </CrudModal>

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
import { useReferenceStore } from '@/stores/reference'
import { icons } from '@/utils/icons'
import { SUBJECTS, SOURCE_TYPES, DIFFICULTY_LEVELS, QUESTION_TYPES } from '@/utils/constants'
import request from '@/api/request'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()
const refStore = useReferenceStore()

const loading = ref(false)
const questions = ref([])
const categories = ref([])
const knowledgeKps = ref([])
const basketIds = ref([])
const detailId = ref(null)
const filters = ref({ subject: '', grade: '', difficulty: '', category_id: '', source: '' })

// Generate modal
const showGenerate = ref(false)
const genLoading = ref(false)
const genResult = ref('')
const genForm = ref({ kp_name: '', grade: '五年级', subject: '数学', difficulty: '中等', count: 5 })

// Category modal
const showCategories = ref(false)
const newCatName = ref('')

// Manual add modal
const showAdd = ref(false)
const addForm = ref({ title: '', type: '计算题', difficulty: 2, grade: '五年级', subject: '数学', kp_name: '', answer: '', analysis: '' })

// ── Navigation ──
const user = computed(() => authStore.user || JSON.parse(localStorage.getItem('user') || 'null'))
const role = computed(() => user.value?.role || 'research')
const researchNav = [{ key: 'knowledge', label: '知识库', icon: icons.knowledge },{ key: 'qbank', label: '题库', icon: icons.qbank },{ key: 'ai', label: 'AI', icon: icons.ai },{ key: 'diagnosis', label: '诊断', icon: icons.diagnosis },{ key: 'me', label: '我的', icon: icons.home }]
const superNav = [{ key: 'dashboard', label: '总览', icon: icons.dashboard },{ key: 'knowledge', label: '知识库', icon: icons.knowledge },{ key: 'qbank', label: '题库', icon: icons.qbank },{ key: 'ai', label: 'AI', icon: icons.ai },{ key: 'system', label: '系统', icon: icons.settings },{ key: 'diagnosis', label: '诊断', icon: icons.diagnosis },{ key: 'me', label: '我的', icon: icons.home }]
const navItems = computed(() => role.value === 'super' ? superNav : researchNav)
function onNav(key) { const map = { dashboard:'/admin/dashboard',knowledge:'/admin/knowledge',qbank:'/admin/qbank',ai:'/admin/ai',diagnosis:'/admin/diagnosis',system:'/admin/system',me:'/admin/me' }; if(map[key]) router.push(map[key]) }

// ── Computed ──
const basketCount = computed(() => basketIds.value.length)
const filteredQuestions = computed(() => questions.value)

// ── Helpers ──
function diffLabel(d) { return d===1?'基础':d===3?'拔高':'中等' }
function diffColor(d) { return d===1?'background:#D1FAE5;color:#065F46':d===3?'background:#FEE2E2;color:#991B1B':'background:#FEF3C7;color:#92400E' }
function showToast(m) { appStore.showToast(m) }

// ── Fetch ──
async function fetchQuestions() {
  loading.value = true
  try {
    const params = {}
    Object.entries(filters.value).forEach(([k,v]) => { if(v) params[k] = v })
    const res = await questionsAPI.getList(params)
    questions.value = res?.items || res?.data || (Array.isArray(res) ? res : [])
  } catch { questions.value = [] }
  finally { loading.value = false }
}
async function fetchCategories() {
  try { const res = await request.get('/questions/categories'); categories.value = Array.isArray(res) ? res : (res?.items||res?.data||[]) } catch {}
}
async function fetchKnowledgeFlat() {
  try { const res = await knowledgeAPI.getTree(); const nodes = res?.items||res?.data||[]; knowledgeKps.value = [...new Set(nodes.map(n=>n.name).filter(Boolean))] } catch {}
}

// ── Basket ──
function toggleBasket(id) { const i = basketIds.value.indexOf(id); i>=0 ? basketIds.value.splice(i,1) : basketIds.value.push(id) }
function clearBasket() { basketIds.value = [] }

// ── Detail ──
function toggleDetail(q) { detailId.value = detailId.value === q.id ? null : q.id }

// ── Category ──
async function setCategory(qid, cid) { if(!cid) return; try { await request.put(`/questions/${qid}/category?category_id=${cid}`); showToast('分类已更新'); fetchQuestions() } catch { showToast('更新失败') } }
async function createCategory() { if(!newCatName.value.trim()) return; try { await request.post('/questions/categories',{name:newCatName.value.trim()}); newCatName.value=''; fetchCategories(); showToast('分类已创建') } catch { showToast('创建失败') } }
async function deleteCategory(c) { if(!confirm('删除分类：'+c.name+'?')) return; try { await request.delete(`/questions/categories/${c.id}`); fetchCategories(); showToast('已删除') } catch { showToast('删除失败') } }

// ── AI Generate ──
function openGenerate() { showGenerate.value = true; genResult.value = '' }
async function doGenerate() {
  if(!genForm.value.kp_name) { showToast('请输入知识点'); return }
  genLoading.value = true; genResult.value = ''
  try {
    const res = await request.post('/questions/generate', genForm.value)
    genResult.value = `✅ 已生成 ${res.count} 道题（批次#${res.batch_id}），待审核入库`
    fetchQuestions()
  } catch(e) { genResult.value = '❌ 生成失败: '+(e?.response?.data?.detail||e?.message) }
  finally { genLoading.value = false }
}

// ── PDF Export ──
function exportPDF() {
  const qs = filteredQuestions.value; if(!qs.length) return
  const items = qs.map((q,i) => `<div style="padding:10px 0;border-bottom:1px solid #e5e7eb">
    <div style="font-weight:600;font-size:13px">${i+1}. ${q.title||''}</div>
    <div style="font-size:11px;color:#6b7280;margin-top:4px">类型:${q.type||''} | ${q.grade||''}·${q.subject||''} | ${q.kp_name||''} | ${diffLabel(q.difficulty)} | ${q.category_name||''}</div>
    ${q.answer ? `<div style="font-size:11px;color:#059669;margin-top:2px">答案: ${q.answer}</div>`:''}
    ${q.analysis ? `<div style="font-size:11px;color:#6b7280;margin-top:2px">解析: ${q.analysis}</div>`:''}
  </div>`).join('')
  const html = `<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><title>题库导出</title><style>body{font-family:sans-serif;padding:16px;max-width:700px;margin:0 auto}h1{font-size:18px;text-align:center}.footer{text-align:center;font-size:10px;color:#d1d5db;margin-top:20px;padding-top:10px;border-top:1px solid #e5e7eb}@media print{body{padding:0}}</style></head><body><h1>📚 题库导出</h1><div style="font-size:11px;color:#9ca3af;text-align:center;margin-bottom:12px">${qs.length} 题 · ${new Date().toLocaleDateString('zh')}</div>${items}<div class="footer">由AI学习诊断系统生成</div></body></html>`
  const blob = new Blob([html],{type:'text/html;charset=utf-8'})
  const url = URL.createObjectURL(blob)
  const w = window.open(url,'_blank')
  if(w) w.onload = () => { w.print() }
  setTimeout(() => URL.revokeObjectURL(url), 60000)
  showToast('PDF已生成')
}

// ── Manual Add ──
function handleAdd() { showAdd.value = true }
async function doAddQuestion() {
  if (!addForm.value.title.trim()) { showToast('请输入题目内容'); return }
  try {
    await questionsAPI.create({
      title: addForm.value.title.trim(), type: addForm.value.type,
      subject: addForm.value.subject, grade: addForm.value.grade,
      difficulty: addForm.value.difficulty, kp_name: addForm.value.kp_name,
      answer: addForm.value.answer, analysis: addForm.value.analysis,
      source: '本地题库',
    })
    showAdd.value = false
    addForm.value = { title: '', type: '计算题', difficulty: 2, grade: '五年级', subject: '数学', kp_name: '', answer: '', analysis: '' }
    fetchQuestions(); showToast('题目已添加')
  } catch { showToast('添加失败') }
}
function editQuestion(q) { showToast('编辑题目: '+q.id) }
async function deleteQuestion(q) { if(!confirm('删除题目：'+q.title?.slice(0,30)+'...?')) return; try { await questionsAPI.remove(q.id); fetchQuestions(); showToast('已删除') } catch { showToast('删除失败') } }

onMounted(async () => {
  await refStore.fetchAll()
  fetchQuestions()
  fetchCategories()
  fetchKnowledgeFlat()
})
</script>

<style scoped>
.filter-bar { display:flex;gap:4px;overflow-x:auto;margin-bottom:8px;padding-bottom:4px;-webkit-overflow-scrolling:touch }
.filter-bar::-webkit-scrollbar { display:none }
.filter-select { height:30px;border:1px solid var(--gray-200);border-radius:6px;padding:0 6px;font-size:11px;background:#fff;flex-shrink:0;min-width:60px }
.q-card { background:#fff;border-radius:8px;padding:10px 12px;margin-bottom:6px;box-shadow:0 1px 2px rgba(0,0,0,.04);cursor:pointer }
.q-card:active { background:var(--gray-50) }
.tag-sm { font-size:9px;padding:1px 5px;border-radius:3px;background:var(--gray-100);color:var(--gray-600) }
.overlay { position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:300;display:flex;align-items:flex-end }
.bottom-sheet { background:#fff;border-radius:12px 12px 0 0;width:100%;max-width:420px;margin:0 auto;max-height:80vh;display:flex;flex-direction:column;animation:slideUp .3s }
@keyframes slideUp { from{transform:translateY(100%)} to{transform:translateY(0)} }
.sheet-handle { width:36px;height:4px;background:var(--gray-300);border-radius:2px;margin:12px auto 8px }
.sheet-title { font-size:16px;font-weight:600;text-align:center;padding:0 16px 12px }
.sheet-body { flex:1;overflow-y:auto;padding:0 16px }
.sheet-footer { display:flex;gap:12px;padding:16px;border-top:1px solid var(--gray-200) }
.sheet-footer .btn { flex:1 }
.fixed-add-bar { position:fixed;bottom:62px;left:50%;transform:translateX(-50%);width:100%;max-width:420px;background:#fff;border-top:1px solid var(--gray-200);padding:8px 12px;z-index:90;display:flex;box-shadow:0 -2px 8px rgba(0,0,0,.06) }
.input-group { margin-bottom:10px }
.input-group label { display:block;font-size:11px;color:var(--gray-500);margin-bottom:3px }
.input { width:100%;height:40px;border:1px solid var(--gray-200);border-radius:6px;padding:0 10px;font-size:13px;box-sizing:border-box }
.select { appearance:auto }
</style>
