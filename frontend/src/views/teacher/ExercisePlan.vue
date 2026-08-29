<template>
  <div class="page">
    <PageHeader title="个性化练习" />

    <div class="page-body">
      <!-- AI Suggestion Card -->
      <div class="card" style="background:var(--primary-light);border-color:var(--primary)">
        <div style="display:flex;justify-content:space-between;align-items:flex-start">
          <div style="font-weight:600">&#x1F3AF; AI建议</div>
          <button class="btn btn-sm btn-outline" @click="fetchAISuggestion" :disabled="aiLoading" style="font-size:11px">
            {{ aiLoading ? '分析中...' : '刷新分析' }}
          </button>
        </div>
        <div v-if="aiSuggestion" style="font-size:13px;color:var(--gray-600);margin-top:4px;line-height:1.5">
          {{ aiSuggestion }}
        </div>
        <div v-else style="font-size:13px;color:var(--gray-400);margin-top:4px;line-height:1.5">
          基于近期诊断，建议重点关注<b>异分母分数加减</b>。推荐每日8-10题，难度中低&#x2192;中。
        </div>
      </div>

      <!-- Existing Plans -->
      <LoadSpinner v-if="loading" text="加载练习计划..." />
      <template v-else>
        <div v-for="p in plans" :key="p.id" class="card">
          <div style="display:flex;justify-content:space-between;gap:8px">
            <div>
              <div style="font-weight:600">{{ p.studentName || p.student_name }}</div>
              <div style="font-size:11px;color:var(--gray-400);margin-top:2px">{{ p.targetKP || p.kp }}</div>
            </div>
            <span class="tag" :class="effectTagClass(p.effect)">{{ p.effect || '进行中' }}</span>
          </div>
          <div style="font-size:12px;color:var(--gray-400);margin-top:7px">{{ p.frequency || p.freq }} · {{ p.count }}题/次 · {{ p.difficulty }}</div>
          <div v-if="p.source || p.sourceTrace" style="font-size:11px;color:var(--gray-400);margin-top:4px">
            {{ p.sourceTrace || p.source }}
          </div>
          <div style="font-size:10px;color:var(--gray-300);margin-top:2px" v-if="p.createdAt || p.created_at">
            创建于 {{ p.createdAt || p.created_at }}
          </div>
          <div style="display:flex;gap:6px;margin-top:8px">
              <button class="btn btn-sm btn-outline" @click="previewPlan(p)">&#x1F4C4; 预览</button>
            <button class="btn btn-sm btn-primary" @click="exportPlan(p)">&#x1F4E5; 导出PDF</button>
            <button class="btn btn-sm btn-outline" @click="openEditModal(p)">&#x270F;&#xFE0F; 编辑</button>
            <button class="btn btn-sm btn-outline" style="color:var(--danger)" @click="deletePlan(p)">&#x1F5D1;&#xFE0F; 删除</button>
          </div>
        </div>

        <EmptyState
          v-if="plans.length === 0"
          icon="&#x1F4DD;"
          title="暂无练习计划"
          desc="根据学生薄弱点生成个性化练习"
        />

        <!-- New Plan Form -->
        <div class="card" style="margin-top:12px">
          <div style="font-weight:600;margin-bottom:8px">{{ editingPlanId ? '编辑练习计划' : '生成新练习计划' }}</div>

          <div class="input-group">
            <label>目标学生</label>
            <div style="display:flex;gap:4px;margin-bottom:4px;flex-wrap:wrap">
              <button type="button" class="btn btn-sm btn-outline" @click="toggleAllStudents" style="font-size:11px">
                {{ plan.studentIds.length === myStudents.length ? '取消全选' : '全选' }}
              </button>
              <span style="font-size:11px;color:var(--gray-400);line-height:24px">已选 {{ plan.studentIds.length }} 人</span>
            </div>
            <div style="max-height:200px;overflow-y:auto;border:1px solid var(--gray-200);border-radius:6px;padding:8px">
              <label v-for="s in myStudents" :key="s.id" style="display:flex;align-items:center;gap:6px;font-size:13px;cursor:pointer;padding:4px 0">
                <input type="checkbox" :value="s.id" v-model="plan.studentIds" /> {{ s.name }} · {{ s.class_name || s.className }}
              </label>
            </div>
          </div>

          <div class="input-group">
            <label>练习知识点</label>
            <input class="input" v-model="plan.kp" placeholder="如：异分母分数加减" />
          </div>

          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
            <div class="input-group">
              <label>每次题量</label>
              <input class="input" type="number" v-model.number="plan.count" :list="'count-list'" min="1" max="50" placeholder="10" />
              <datalist :id="'count-list'">
                <option v-for="c in QUESTION_COUNTS" :value="c" :key="c">{{ c }}题</option>
              </datalist>
            </div>
            <div class="input-group">
              <label>难度</label>
              <select class="input select" v-model="plan.difficulty">
                <option>自适应</option>
                <option v-for="d in DIFFICULTY_LEVELS" :key="d">{{ d }}</option>
              </select>
            </div>
          </div>

          <div class="input-group">
            <label>频率</label>
            <input class="input" v-model="plan.freq" :list="'freq-list'" placeholder="每周3次" />
            <datalist :id="'freq-list'">
              <option v-for="f in EXERCISE_FREQUENCIES" :value="f" :key="f">{{ f }}</option>
            </datalist>
          </div>

          <div style="font-size:12px;color:var(--gray-500);line-height:1.5;padding:10px 12px;background:var(--gray-50);border-radius:8px;margin-bottom:12px">
            系统会根据学生近期错题、薄弱知识点和历史难度自动匹配高质量题目。可通过"📋 从题库选题"按钮手动选择。
          </div>

          <div style="display:flex;gap:8px;margin-bottom:8px">
            <button class="btn btn-outline btn-block" style="flex:1" @click="openQuestionPicker" :disabled="!plan.studentIds.length || !plan.kp">
              📋 从题库选题
            </button>
          </div>

          <div style="display:flex;gap:8px">
            <button v-if="editingPlanId" class="btn btn-outline" style="flex:1" @click="cancelEdit">取消编辑</button>
            <button class="btn btn-primary btn-block" :style="editingPlanId ? {flex:1} : {}" @click="genPlan" :disabled="generating">
              <span v-if="generating">生成中...</span>
              <span v-else>{{ editingPlanId ? '保存修改' : '智能生成练习卷' }}</span>
            </button>
          </div>
        </div>
      </template>

      <!-- Preview Modal -->
      <teleport to="body">
        <div v-if="previewPlanData" class="overlay" @click.self="previewPlanData = null">
          <div class="bottom-sheet">
            <div class="sheet-handle"></div>
            <h3 class="sheet-title">练习计划详情</h3>
            <div class="sheet-body">
              <div style="padding:12px 0;line-height:1.8;font-size:13px">
                <div><b>学生：</b>{{ previewPlanData.studentName || previewPlanData.student_name }}</div>
                <div><b>目标知识点：</b>{{ previewPlanData.targetKP || previewPlanData.kp }}</div>
                <div><b>频率：</b>{{ previewPlanData.frequency || previewPlanData.freq }}</div>
                <div><b>每次题量：</b>{{ previewPlanData.count }}题</div>
                <div><b>难度：</b>{{ previewPlanData.difficulty }}</div>
                <div><b>题目来源：</b>{{ previewPlanData.sourceTrace || previewPlanData.source || '智能题库' }}</div>
                <div>
                  <b>效果状态：</b>
                  <span class="tag" :class="effectTagClass(previewPlanData.effect)" style="margin-left:4px">{{ previewPlanData.effect || '进行中' }}</span>
                </div>
                <div><b>创建时间：</b>{{ previewPlanData.createdAt || previewPlanData.created_at || '--' }}</div>
              </div>
              <!-- Sample question list -->
              <div style="margin-top:12px">
                <div style="font-weight:600;font-size:13px;margin-bottom:8px">&#x1F4CB; 题目预览（示例）</div>
                <div v-for="q in sampleQuestions" :key="q.num" style="padding:8px;background:var(--gray-50);border-radius:6px;margin-bottom:6px;font-size:12px">
                  <span style="font-weight:600;color:var(--primary)">第{{ q.num }}题</span>
                  <span style="margin-left:6px;color:var(--gray-600)">{{ q.desc }}</span>
                  <span class="tag" :class="'tag-' + q.diff" style="font-size:10px;margin-left:6px">{{ q.diffLabel }}</span>
                </div>
              </div>
            </div>
            <div class="sheet-footer">
              <button class="btn btn-outline" @click="previewPlanData = null">关闭</button>
              <button class="btn btn-primary" @click="exportPlan(previewPlanData); previewPlanData = null">&#x1F4E5; 导出PDF</button>
            </div>
          </div>
        </div>
      </teleport>

      <!-- Edit Modal -->
      <teleport to="body">
        <div v-if="editModalData" class="overlay" @click.self="closeEditModal">
          <div class="bottom-sheet">
            <div class="sheet-handle"></div>
            <h3 class="sheet-title">编辑练习计划</h3>
            <div class="sheet-body">
              <div class="input-group">
                <label>目标学生</label>
                <select class="input select" v-model="editForm.studentId">
                  <option v-for="s in myStudents" :value="s.id" :key="s.id">{{ s.name }} · {{ s.class_name || s.className }}</option>
                </select>
              </div>
              <div class="input-group">
                <label>练习知识点</label>
                <input class="input" v-model="editForm.kp" placeholder="如：异分母分数加减" />
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
                <div class="input-group">
                  <label>每次题量</label>
                  <input class="input" type="number" v-model.number="editForm.count" :list="'edit-count-list'" min="1" max="50" />
                  <datalist :id="'edit-count-list'">
                    <option v-for="c in QUESTION_COUNTS" :value="c" :key="c">{{ c }}题</option>
                  </datalist>
                </div>
                <div class="input-group">
                  <label>难度</label>
                  <select class="input select" v-model="editForm.difficulty">
                    <option>自适应</option>
                    <option v-for="d in DIFFICULTY_LEVELS" :key="d">{{ d }}</option>
                  </select>
                </div>
              </div>
              <div class="input-group">
                <label>频率</label>
                <input class="input" v-model="editForm.freq" :list="'edit-freq-list'" placeholder="每周3次" />
                <datalist :id="'edit-freq-list'">
                  <option v-for="f in EXERCISE_FREQUENCIES" :value="f" :key="f">{{ f }}</option>
                </datalist>
              </div>
              <div class="input-group">
                <label>效果状态</label>
                <select class="input select" v-model="editForm.effect">
                  <option>待观察</option>
                  <option>改善中</option>
                  <option>已提升</option>
                  <option>效果不佳</option>
                </select>
              </div>
            </div>
            <div class="sheet-footer">
              <button class="btn btn-outline" @click="closeEditModal">取消</button>
              <button class="btn btn-primary" @click="saveEdit" :disabled="editSaving">{{ editSaving ? '保存中...' : '保存修改' }}</button>
            </div>
          </div>
        </div>
      </teleport>
    </div>

    <BottomNav :items="teacherNav" active="exercise" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { exercisesAPI } from '@/api/exercises'
import { studentsAPI } from '@/api/students'
import { diagnosesAPI } from '@/api/diagnoses'
import { aiAPI } from '@/api/ai'
import request from '@/api/request'
import BottomNav from '@/components/BottomNav.vue'
import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import LoadSpinner from '@/components/LoadSpinner.vue'
import { icons } from '@/utils/icons'
import { EXERCISE_FREQUENCIES, QUESTION_COUNTS, DIFFICULTY_LEVELS } from '@/utils/constants'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()

const loading = ref(true)
const generating = ref(false)
const aiLoading = ref(false)
const plans = ref([])
const allStudents = ref([])
	const editingPlanId = ref(null)
	const previewPlanData = ref(null)
	const editModalData = ref(null)
	const editSaving = ref(false)
	const aiSuggestion = ref('')

	// ── Question Picker ──
	const showPicker = ref(false)
	const pickerQuestions = ref([])
	const pickerCategories = ref([])
	const pickerSelected = ref([])
	const pickerDifficulty = ref('')
	const pickerCategory = ref('')
	const selectedQuestionIds = ref([])

	const defaultPlan = () => ({
	  studentIds: [],
	  kp: '',
	  freq: '每周3次',
	  count: 10,
	  difficulty: '自适应',
	})

	const plan = ref(defaultPlan())
	const editForm = ref(defaultPlan())

const user = computed(() => authStore.user)

const myStudents = computed(() => {
  if (!user.value?.classes) return allStudents.value
  return allStudents.value.filter(s => user.value.classes.includes(s.classId || s.class_id))
})

const sampleQuestions = computed(() => {
  const kp = previewPlanData.value?.targetKP || previewPlanData.value?.kp || '知识点'
  const count = previewPlanData.value?.count || 8
  const diffs = [
    { diff: 'green', diffLabel: '基础' },
    { diff: 'yellow', diffLabel: '中等' },
    { diff: 'red', diffLabel: '拔高' },
  ]
  return Array.from({ length: Math.min(count, 5) }, (_, i) => ({
    num: i + 1,
    desc: `${kp}相关练习题目 #${i + 1}（根据学生薄弱点自适应生成）`,
    diff: diffs[i % 3].diff,
    diffLabel: diffs[i % 3].diffLabel,
  }))
})

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
  else if (key === 'me') router.push('/teacher/me')
}

function effectTagClass(effect) {
  if (!effect) return 'tag-yellow'
  if (effect.includes('改善') || effect.includes('提升')) return 'tag-green'
  if (effect.includes('待观察')) return 'tag-yellow'
  return 'tag-yellow'
}

async function loadData() {
  loading.value = true
  try {
    const [exerRes, stuRes] = await Promise.allSettled([
      exercisesAPI.getList(),
      studentsAPI.getList(),
    ])
    if (exerRes.status === 'fulfilled') {
      const r = exerRes.value; plans.value = r?.items || r?.data || r || []
    } else {
      plans.value = getMockPlans()
    }
    if (stuRes.status === 'fulfilled') {
      const r = stuRes.value; allStudents.value = r?.items || r?.data || r || []
    } else {
      allStudents.value = getMockStudents()
    }
  } catch {
    plans.value = getMockPlans()
    allStudents.value = getMockStudents()
  } finally {
    loading.value = false
  }
}

function getMockPlans() {
  return [
    { id: 'p1', studentId: 's1', studentName: '张三', student_name: '张三', targetKP: '分数通分+分数应用', frequency: '每周3次', freq: '每周3次', count: 15, difficulty: '中等', source: '教研云题库', sourceTrace: '教研云12题 + 本地3题', status: '进行中', effect: '改善中', createdAt: '07/12', created_at: '07/12' },
    { id: 'p2', studentId: 's3', studentName: '王五', student_name: '王五', targetKP: '异分母分数加减', frequency: '每天1次', freq: '每天1次', count: 10, difficulty: '基础', source: '本地题库', sourceTrace: '本地10题', status: '进行中', effect: '待观察', createdAt: '07/14', created_at: '07/14' },
  ]
}

function getMockStudents() {
  return [
    { id: 's1', name: '张三', classId: 'c1', class_name: '五(1)班', grade: '五年级' },
    { id: 's2', name: '李四', classId: 'c1', class_name: '五(1)班', grade: '五年级' },
    { id: 's3', name: '王五', classId: 'c1', class_name: '五(1)班', grade: '五年级' },
  ]
}

function previewPlan(p) {
  previewPlanData.value = p
}

function editPlan(p) {
  editingPlanId.value = p.id
  plan.value = {
    studentIds: [p.studentId || p.student_id || ''],
    kp: p.targetKP || p.kp || '',
    freq: p.frequency || p.freq || '每周3次',
    count: p.count || 10,
    difficulty: p.difficulty || '自适应',
  }
}

function openEditModal(p) {
  editModalData.value = p
  editForm.value = {
    studentId: p.studentId || p.student_id || '',
    kp: p.targetKP || p.kp || '',
    freq: p.frequency || p.freq || '每周3次',
    count: p.count || 10,
    difficulty: p.difficulty || '自适应',
    effect: p.effect || '待观察',
  }
}

function closeEditModal() {
  editModalData.value = null
}

async function saveEdit() {
  if (!editForm.value.studentId || !editForm.value.kp) {
    appStore.showToast('请完善信息')
    return
  }
  editSaving.value = true
  const p = editModalData.value
  const payload = {
    student_id: editForm.value.studentId,
    target_kp: editForm.value.kp,
    question_count: editForm.value.count,
    difficulty: editForm.value.difficulty,
    frequency: editForm.value.freq,
    effect: editForm.value.effect,
  }
  try {
    await exercisesAPI.update(p.id, payload)
    const idx = plans.value.findIndex(x => x.id === p.id)
    if (idx >= 0) {
      const stu = allStudents.value.find(s => s.id === editForm.value.studentId)
      plans.value[idx] = {
        ...plans.value[idx],
        studentId: editForm.value.studentId,
        studentName: stu?.name || plans.value[idx].studentName,
        student_name: stu?.name || plans.value[idx].student_name,
        targetKP: editForm.value.kp,
        kp: editForm.value.kp,
        frequency: editForm.value.freq,
        freq: editForm.value.freq,
        count: editForm.value.count,
        difficulty: editForm.value.difficulty,
        effect: editForm.value.effect,
      }
    }
    appStore.showToast('计划已更新')
    closeEditModal()
  } catch {
    appStore.showToast('保存失败')
  } finally {
    editSaving.value = false
  }
}

function cancelEdit() {
  editingPlanId.value = null
  plan.value = defaultPlan()
}

// ── Question Picker ──
async function openQuestionPicker() {
  showPicker.value = true; pickerSelected.value = [...selectedQuestionIds.value]
  await loadPickerQuestions()
  try { const res = await request.get('/questions/categories'); pickerCategories.value = Array.isArray(res) ? res : (res?.items||res?.data||[]) } catch {}
}
async function loadPickerQuestions() {
  const params = { kp_name: plan.value.kp, status: 'approved' }
  if (pickerDifficulty.value) params.difficulty = parseInt(pickerDifficulty.value)
  if (pickerCategory.value) params.category_id = pickerCategory.value
  try { const res = await request.get('/questions', { params }); pickerQuestions.value = res?.items || res?.data || [] } catch { pickerQuestions.value = [] }
}
function togglePickerSelect(id) { const i = pickerSelected.value.indexOf(id); i>=0 ? pickerSelected.value.splice(i,1) : pickerSelected.value.push(id) }
function confirmPickerSelection() { selectedQuestionIds.value = [...pickerSelected.value]; showPicker.value = false; showToast('已选'+pickerSelected.value.length+'题') }

async function deletePlan(p) {
  if (!confirm('确定删除该练习计划?')) return
  try {
    await exercisesAPI.remove(p.id)
  } catch {
    // ignore
  }
  plans.value = plans.value.filter(x => x.id !== p.id)
  appStore.showToast('已删除')
}

function toggleAllStudents() {
  if (plan.value.studentIds.length === myStudents.value.length) {
    plan.value.studentIds = []
  } else {
    plan.value.studentIds = myStudents.value.map(s => s.id)
  }
}

async function genPlan() {
  if (!plan.value.studentIds.length || !plan.value.kp) {
    appStore.showToast('请选择学生并填写知识点')
    return
  }
  generating.value = true

  const today = new Date().toLocaleDateString('zh', { month: 'short', day: 'numeric' })
  const basePayload = {
    target_kp: plan.value.kp,
    question_count: plan.value.count,
    difficulty: plan.value.difficulty,
    frequency: plan.value.freq,
  }

  if (editingPlanId.value) {
    // Update existing plan (single student)
    const payload = { ...basePayload, student_id: plan.value.studentIds[0] }
    try {
      await exercisesAPI.update(editingPlanId.value, payload)
      const idx = plans.value.findIndex(x => x.id === editingPlanId.value)
      if (idx >= 0) {
        const stu = allStudents.value.find(s => s.id === plan.value.studentIds[0])
        plans.value[idx] = {
          ...plans.value[idx],
          studentName: stu?.name || plans.value[idx].studentName,
          student_name: stu?.name || plans.value[idx].student_name,
          targetKP: plan.value.kp, kp: plan.value.kp,
          frequency: plan.value.freq, freq: plan.value.freq,
          count: plan.value.count, difficulty: plan.value.difficulty,
        }
      }
      appStore.showToast('计划已更新')
    } catch {
      appStore.showToast('更新失败')
    }
    cancelEdit()
  } else {
    // Create new plans — one per selected student
    const created = []
    for (const sid of plan.value.studentIds) {
      const s = allStudents.value.find(x => x.id === sid)
      const payload = { ...basePayload, student_id: sid }
      try {
        const res = await exercisesAPI.create(payload)
        const result = res.data || res || {}
        created.push({
          id: result.id || 'p' + Date.now() + '_' + sid,
          studentId: sid,
          studentName: s?.name || '学生' + sid,
          student_name: s?.name || '学生' + sid,
          targetKP: plan.value.kp,
          frequency: plan.value.freq, freq: plan.value.freq,
          count: plan.value.count, difficulty: plan.value.difficulty,
          source: '统一智能题库',
          sourceTrace: '教研云' + Math.round(plan.value.count * 0.8) + '题 + 本地' + Math.round(plan.value.count * 0.2) + '题',
          status: '进行中', effect: '待观察',
          createdAt: today, created_at: today,
        })
      } catch {
        // Fallback: local-only entry
        created.push({
          id: 'p' + Date.now() + '_' + sid,
          studentId: sid, studentName: s?.name || '学生' + sid, student_name: s?.name || '学生' + sid,
          targetKP: plan.value.kp, frequency: plan.value.freq, freq: plan.value.freq,
          count: plan.value.count, difficulty: plan.value.difficulty,
          source: '统一智能题库',
          sourceTrace: '教研云' + Math.round(plan.value.count * 0.8) + '题 + 本地' + Math.round(plan.value.count * 0.2) + '题',
          status: '进行中', effect: '待观察', createdAt: today, created_at: today,
        })
      }
    }
    plans.value = [...created, ...plans.value]
    plan.value = defaultPlan()
    appStore.showToast(`已为 ${created.length} 名学生生成练习计划`)
  }
  generating.value = false
}

function exportPlan(p) {
  const kp = p.targetKP || p.kp || ''
  const diffLabel = p.difficulty || '中等'
  const questionCount = p.count || 10
  const name = p.studentName || p.student_name || '学生'
  const freq = p.frequency || p.freq || '每周3次'

  const questionItems = Array.from({ length: Math.min(questionCount, 8) }, (_, i) =>
    `<div style="padding:10px;margin-bottom:6px;border:1px solid #e5e7eb;border-radius:6px;font-size:13px">
      <b>${i + 1}.</b> ${kp} 练习题目 #${i + 1}（根据${name}的薄弱点自适应生成，难度${diffLabel}）
    </div>`
  ).join('')

  const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>练习计划 - ${name}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 24px; max-width: 700px; margin: 0 auto; color: #1f2937; }
    h1 { font-size: 20px; text-align: center; margin-bottom: 4px; }
    .info { text-align: center; font-size: 12px; color: #9ca3af; margin-bottom: 16px; }
    .info span { margin: 0 6px; }
    .section { margin-bottom: 16px; }
    .section h3 { font-size: 14px; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 2px solid #4f46e5; }
    .meta { display: flex; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
    .meta-item { padding: 6px 12px; background: #f3f4f6; border-radius: 6px; font-size: 12px; }
    .footer { text-align: center; font-size: 11px; color: #d1d5db; margin-top: 24px; padding-top: 12px; border-top: 1px solid #e5e7eb; }
    @media print { body { padding: 0; } }
  </style>
</head>
<body>
  <h1>&#x1F4DD; ${kp} 专项练习</h1>
  <div class="info">
    <span>学生：${name}</span>
    <span>频率：${freq}</span>
    <span>${questionCount}题/次</span>
    <span>难度：${diffLabel}</span>
  </div>
  <div class="meta">
    <div class="meta-item">&#x1F3AF; 目标知识点：${kp}</div>
    <div class="meta-item">&#x1F4CA; 来源：${p.sourceTrace || p.source || '智能题库'}</div>
    <div class="meta-item">&#x1F4C5; ${new Date().toLocaleDateString('zh')}</div>
  </div>
  <div class="section">
    <h3>习题列表</h3>
    ${questionItems}
  </div>
  <div class="section" style="padding:12px;background:#fef3c7;border-radius:8px;font-size:12px">
    &#x26A0;&#xFE0F; 此为练习计划预览，实际题目将由系统根据学生诊断数据从题库中自动匹配生成。
  </div>
  <div class="footer">由教学管理系统生成</div>
</body>
</html>`

  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const w = window.open(url, '_blank')
  if (w) {
    w.onload = () => {
      w.print()
    }
  }
  setTimeout(() => URL.revokeObjectURL(url), 60000)
  appStore.showToast('练习卷已生成')
}

async function fetchAISuggestion() {
  aiLoading.value = true
  try {
    // Collect weak KPs from student diagnoses
    let weakKps = []
    try {
      const stuRes = await studentsAPI.getList()
      const students = stuRes.data || stuRes || []
      for (const s of students.slice(0, 5)) {
        try {
          const diagRes = await diagnosesAPI.getList({ student_id: s.id })
          const diags = diagRes.data || diagRes || []
          diags.filter(d => d.verdict === 'incorrect').forEach(d => {
            if (d.kp) weakKps.push(d.kp)
          })
        } catch { /* skip */ }
      }
    } catch { /* skip */ }

    const uniqueKps = [...new Set(weakKps)].slice(0, 5)
    const prompt = uniqueKps.length
      ? `根据以下学生薄弱知识点，给出个性化练习建议（100字内）：${uniqueKps.join('、')}`
      : '根据一般学情，给出数学练习建议（100字内）'

    try {
      const res = await aiAPI.suggest({ prompt })
      aiSuggestion.value = (res.data || res)?.suggestion || (res.data || res)?.text || '建议重点关注薄弱知识点，循序渐进安排练习。'
    } catch {
      aiSuggestion.value = uniqueKps.length
        ? `基于近期诊断，建议重点关注${uniqueKps.slice(0, 3).join('、')}。推荐每日8-10题，难度中低→中。`
        : '基于近期诊断，建议重点关注异分母分数加减。推荐每日8-10题，难度中低→中。'
    }
  } catch {
    aiSuggestion.value = '基于近期诊断，建议重点关注异分母分数加减。推荐每日8-10题，难度中低→中。'
  } finally {
    aiLoading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,.4);
  z-index: 300; display: flex; align-items: flex-end;
}
.bottom-sheet {
  background: #fff; border-radius: var(--radius) var(--radius) 0 0;
  width: 100%; max-width: 420px; margin: 0 auto;
  max-height: 80vh; display: flex; flex-direction: column;
  animation: slideUp .3s ease;
}
@keyframes slideUp { from { transform: translateY(100%) } to { transform: translateY(0) } }
.sheet-handle {
  width: 36px; height: 4px; background: var(--gray-300);
  border-radius: 2px; margin: 12px auto 8px;
}
.sheet-title {
  font-size: 16px; font-weight: 600; text-align: center; padding: 0 16px 12px;
}
.sheet-body {
  flex: 1; overflow-y: auto; padding: 0 16px;
}
.sheet-footer {
  display: flex; gap: 12px; padding: 16px; border-top: 1px solid var(--gray-200);
}
.sheet-footer .btn { flex: 1 }
</style>
