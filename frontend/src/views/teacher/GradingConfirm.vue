<template>
  <div class="page">
    <PageHeader title="批改确认" :showBack="true">
      <span style="font-size:12px;color:var(--gray-400)">{{ idx + 1 }}/{{ diags.length }}题</span>
    </PageHeader>

    <div class="split-view" style="flex:1;display:flex;flex-direction:column;overflow:hidden">
      <!-- Top: Simulated Paper Image -->
      <div class="split-top" style="min-height:200px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:13px;text-align:center;padding:16px;background:linear-gradient(135deg,var(--primary),var(--primary-dark))">
        <div>
          &#x1F4C4; 试卷图片区域<br>
          <span style="font-size:11px;opacity:.6">实际产品显示试卷照片+AI标注</span>
          <div style="margin-top:10px;display:flex;flex-wrap:wrap;gap:4px;justify-content:center">
            <span
              v-for="d in diags" :key="d.num"
              style="padding:2px 6px;border-radius:4px;font-size:11px"
              :style="{background: d.num === cur?.num ? 'rgba(79,70,229,.4)' : 'rgba(255,255,255,.1)'}"
            >{{ d.num }}.{{ verdictIcon(d.verdict) }}</span>
          </div>
        </div>
      </div>

      <div class="split-handle" style="height:8px;background:var(--gray-200);cursor:row-resize;flex-shrink:0"></div>

      <!-- Bottom: Diagnosis Cards -->
      <div class="split-bottom" style="flex:1;overflow-y:auto;padding:10px 14px">
        <LoadSpinner v-if="loading" text="加载诊断数据..." />

        <template v-else>
          <!-- Question Navigation Circles -->
          <div class="question-nav">
            <button
              v-for="d in diags" :key="d.num"
              class="question-nav-item"
              :class="[d.verdict, { active: idx === d.num - 1 }]"
              @click="idx = d.num - 1"
            >{{ d.num }}</button>
          </div>

          <div v-if="cur" class="card fade-in" style="margin-top:10px">
            <!-- Verdict Header -->
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
              <span style="font-size:18px">{{ verdictIcon(cur.verdict) }}</span>
              <span style="font-weight:600">第{{ cur.num }}题: {{ cur.kp }}</span>
              <span class="tag" :class="verdictTag(cur.verdict)">{{ verdictLabel(cur.verdict) }}</span>
            </div>

            <!-- AI Explain -->
            <div style="background:var(--gray-50);border-radius:6px;padding:8px;font-size:13px;margin-bottom:8px">
              <div style="font-size:11px;color:var(--gray-400);margin-bottom:3px">AI识别与分析</div>
              {{ cur.aiExplain }}
            </div>

            <!-- Editable Fields -->
            <div class="input-group">
              <label>识别文本(可修改)</label>
              <textarea class="textarea" v-model="cur.ocrText" style="min-height:46px"></textarea>
            </div>
            <div class="input-group">
              <label>错误步骤(可修改)</label>
              <textarea class="textarea" v-model="cur.wrongStep" style="min-height:46px"></textarea>
            </div>

            <!-- Related KPs -->
            <div style="margin-bottom:10px">
              <div style="font-size:13px;font-weight:500;color:var(--gray-700);margin-bottom:6px">相关知识点</div>
              <span v-for="k in (cur.relatedKps || [])" :key="k" class="tag tag-primary" style="margin-right:4px;margin-bottom:4px">{{ k }}</span>
            </div>

            <!-- Verdict Select -->
            <div class="input-group">
              <label>判定(可修改)</label>
            <select class="input select" v-model="cur.verdict">
              <option v-for="v in VERDICT_OPTIONS" :value="v.value" :key="v.value">{{ verdictIcon(v.value) }} {{ v.label }}</option>
            </select>
            </div>

            <!-- Error Cause - Knowledge -->
            <div class="input-group">
              <label>错因-知识层</label>
            <select class="input select" v-model="cur.errorCause">
              <option value="">无</option>
              <option v-for="e in ERROR_CAUSES_K" :value="e" :key="e">{{ e }}</option>
            </select>
            </div>

            <!-- Error Cause - Skill -->
            <div class="input-group">
              <label>错因-能力层</label>
            <select class="input select" v-model="cur.skillCause">
              <option>无</option>
              <option v-for="e in ERROR_CAUSES_S" :value="e" :key="e">{{ e }}</option>
            </select>
            </div>

            <!-- KP Select -->
            <div class="input-group">
              <label>知识点</label>
              <select class="input select" v-model="cur.kp">
                <option v-for="k in kpOptions" :value="k" :key="k">{{ k }}</option>
              </select>
            </div>

            <!-- Ability Select -->
            <div class="input-group">
              <label>能力维度</label>
            <select class="input select" v-model="cur.ability">
              <option v-for="a in ABILITY_DIMENSIONS" :value="a" :key="a">{{ a }}</option>
            </select>
            </div>

            <!-- Teacher Note -->
            <div class="input-group">
              <label>老师补充说明</label>
              <textarea class="textarea" v-model="cur.teacherNote" placeholder="补充AI未发现的点..." style="min-height:50px"></textarea>
            </div>

            <!-- Typical Checkbox -->
            <label style="display:flex;align-items:center;gap:8px;font-size:13px;margin-bottom:8px;cursor:pointer">
              <input type="checkbox" v-model="cur.typical" /> 标记为典型错题，进入错题本和后续练习
            </label>

            <!-- Confidence Bar -->
            <div style="background:var(--gray-50);border-radius:6px;padding:6px 10px;margin-bottom:8px;display:flex;align-items:center;gap:8px">
              <span style="font-size:11px;color:var(--gray-500)">AI置信度</span>
              <div style="flex:1;height:4px;background:var(--gray-200);border-radius:2px">
                <div :style="{
                  width: (cur.confidence * 100) + '%',
                  height: '100%',
                  background: cur.confidence >= 0.85 ? 'var(--success)' : cur.confidence >= 0.6 ? 'var(--warning)' : 'var(--danger)',
                  borderRadius: '2px'
                }"></div>
              </div>
              <span style="font-size:11px;font-weight:600">{{ parseFloat((cur.confidence * 100).toFixed(1)) }}%</span>
            </div>

            <!-- Action Buttons -->
            <div style="display:flex;gap:6px">
              <button class="btn btn-primary btn-sm" @click="confirm">&#x2713; 确认本题</button>
              <button class="btn btn-outline btn-sm" @click="idx = Math.min(idx + 1, diags.length - 1)">下一题 &#x2192;</button>
            </div>

            <!-- Low Confidence Warning -->
            <div v-if="cur.confidence < 0.6" class="card" style="background:var(--warning-light);border-color:var(--warning);margin-top:8px">
              <div style="font-weight:600;font-size:13px;color:var(--warning)">&#x26A0;&#xFE0F; AI置信度偏低，请人工补充</div>
              <div style="font-size:12px;color:var(--gray-600);margin-top:4px">建议手动确认本题识别文本和知识点是否正确</div>
            </div>
          </div>

          <!-- Batch Confirm -->
          <div style="text-align:center;padding:10px 0;margin-bottom:20px">
            <button class="btn btn-primary" @click="batchConfirm" :disabled="confirmed === diags.length">
              &#x1F4E4; 全部确认({{ confirmed }}/{{ diags.length }})
            </button>
          </div>
        </template>
      </div>
    </div>

    <BottomNav :items="teacherNav" active="tasks" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { diagnosesAPI } from '@/api/diagnoses'
import { tasksAPI } from '@/api/tasks'
import BottomNav from '@/components/BottomNav.vue'
import PageHeader from '@/components/PageHeader.vue'
import LoadSpinner from '@/components/LoadSpinner.vue'
import { icons } from '@/utils/icons'
import { verdictIcon, verdictLabel, verdictTag } from '@/utils/helpers'
import { VERDICT_OPTIONS, ERROR_CAUSES_K, ERROR_CAUSES_S, ABILITY_DIMENSIONS } from '@/utils/constants'
import { knowledgeAPI } from '@/api/knowledge'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()

const loading = ref(true)
const idx = ref(0)
const diags = ref([])
const conf = ref({})

const kpOptions = ref([
  '分数概念', '同分母分数加减', '异分母分数加减', '分数比较',
  '分数与小数互化', '分数乘除法', '分数应用题建模', '分数四则混合运算',
  '分数方程', '综合应用题',
])

const cur = computed(() => diags.value[idx.value] || null)
const confirmed = computed(() => Object.keys(conf.value).length)

const teacherNav = [
  { key: 'students', label: '学生', icon: icons.students },
  { key: 'tasks', label: '任务', icon: icons.tasks },
  { key: 'upload', label: '上传', icon: icons.upload },
  { key: 'exercise', label: '练习', icon: icons.exercise },
  { key: 'me', label: '我的', icon: icons.home },
]

function onNav(key) {
  if (key === 'students') router.push('/teacher/students')
  else if (key === 'upload') router.push('/teacher/upload')
  else if (key === 'exercise') router.push('/teacher/exercise')
  else if (key === 'me') router.push('/teacher/me')
}

async function loadData() {
  loading.value = true
  const taskId = route.params.taskId
  try {
    const res = await diagnosesAPI.getList({ task_id: taskId })
    const data = res.data || res || []
    if (data.length) {
      diags.value = JSON.parse(JSON.stringify(data))
    } else {
      diags.value = getMockDiagnoses()
    }
  } catch {
    diags.value = getMockDiagnoses()
  } finally {
    loading.value = false
  }
  // Fetch KP options from knowledge tree in background
  fetchKpOptions(taskId)
}

async function fetchKpOptions(taskId) {
  try {
    // Try to get the task to know its subject for filtering
    let subject = null
    try {
      const taskRes = await tasksAPI.getById(taskId)
      const task = taskRes.data || taskRes || {}
      subject = task.subject
    } catch { /* fallback */ }

    const kpRes = await knowledgeAPI.getTree()
    const tree = kpRes.data || kpRes || []
    const flat = flattenKnowledgeTree(tree)
    if (subject) {
      // Prefer KPs matching the task's subject
      const filtered = flat.filter(n => n.subject === subject)
      if (filtered.length) {
        kpOptions.value = filtered.map(n => n.name || n.label)
        return
      }
    }
    if (flat.length) {
      kpOptions.value = flat.map(n => n.name || n.label)
    }
  } catch {
    // Keep default kpOptions
  }
}

function flattenKnowledgeTree(nodes, result = []) {
  for (const node of nodes) {
    result.push({ id: node.id, name: node.name || node.label, subject: node.subject })
    if (node.children && node.children.length) {
      flattenKnowledgeTree(node.children, result)
    }
  }
  return result
}

function getMockDiagnoses() {
  return [
    { num: 1, verdict: 'correct', ocrText: '3/8 + 2/8 = 5/8', wrongStep: '无', kp: '分数概念', relatedKps: ['同分母分数加减'], errorCause: '', skillCause: '无', ability: '概念理解能力', aiExplain: '学生正确理解了分数基本概念，过程和结果均正确', confidence: 0.95, typical: false, teacherNote: '' },
    { num: 2, verdict: 'correct', ocrText: '7/9 - 2/9 = 5/9', wrongStep: '无', kp: '同分母分数加减', relatedKps: ['分数概念'], errorCause: '', skillCause: '无', ability: '运算能力', aiExplain: '同分母计算扎实，分母保持不变、分子相减正确', confidence: 0.93, typical: false, teacherNote: '' },
    { num: 3, verdict: 'incorrect', ocrText: '1/3 + 1/2 = 2/5', wrongStep: '未先通分，直接分子分母分别相加', kp: '异分母分数加减', relatedKps: ['通分', '分数基本性质'], errorCause: '概念混淆', skillCause: '程序性知识错误', ability: '概念理解能力', aiExplain: '未通分直接相加。正确做法应先通分为2/6+3/6=5/6', confidence: 0.91, typical: true, teacherNote: '' },
    { num: 4, verdict: 'correct', ocrText: '3/5 > 4/9', wrongStep: '无', kp: '分数比较', relatedKps: ['通分'], errorCause: '', skillCause: '无', ability: '逻辑推理能力', aiExplain: '分数大小比较方法正确，能选择通分后比较', confidence: 0.94, typical: false, teacherNote: '' },
    { num: 5, verdict: 'partially_correct', ocrText: '1/8 = 0.12', wrongStep: '小数换算末位漏写5', kp: '分数与小数互化', relatedKps: ['除法计算'], errorCause: '计算失误', skillCause: 'S型-计算细节错误', ability: '运算能力', aiExplain: '思路正确，但1/8转化为小数时计算错误，应为0.125', confidence: 0.87, typical: false, teacherNote: '' },
    { num: 6, verdict: 'incorrect', ocrText: '剩下部分直接乘总量', wrongStep: '遗漏题干中"剩下的"这一条件', kp: '分数应用题建模', relatedKps: ['单位1识别', '分数乘法'], errorCause: '建模失败', skillCause: '审题偏差', ability: '应用建模能力', aiExplain: '未能将实际问题转化为分数模型，审题遗漏关键条件', confidence: 0.88, typical: true, teacherNote: '' },
    { num: 7, verdict: 'correct', ocrText: '2/5 × 15 = 6', wrongStep: '无', kp: '分数乘法', relatedKps: ['整数乘法'], errorCause: '', skillCause: '无', ability: '运算能力', aiExplain: '分数乘法运算正确，单位处理完整', confidence: 0.96, typical: false, teacherNote: '' },
    { num: 8, verdict: 'incorrect', ocrText: '先算加法再算乘法', wrongStep: '四则混合运算顺序错误', kp: '分数四则混合运算', relatedKps: ['分数乘除法', '运算顺序'], errorCause: '策略不当', skillCause: '程序性知识错误', ability: '逻辑推理能力', aiExplain: '运算顺序错误，未按先乘除后加减的规则', confidence: 0.92, typical: true, teacherNote: '' },
    { num: 9, verdict: 'correct', ocrText: 'x = 3/4', wrongStep: '无', kp: '分数方程', relatedKps: ['等式性质'], errorCause: '', skillCause: '无', ability: '表达规范能力', aiExplain: '分数方程求解步骤完整正确，书写规范', confidence: 0.90, typical: false, teacherNote: '' },
    { num: 10, verdict: 'uncertain', ocrText: '字迹模糊，仅能识别部分步骤', wrongStep: '关键列式区域无法识别', kp: '综合应用题', relatedKps: ['分数应用题建模', '审题能力'], errorCause: '需人工判断', skillCause: '低置信度-需人工补录', ability: '审题能力', aiExplain: '学生作答部分正确但字迹模糊，部分步骤难以确认', confidence: 0.55, typical: false, teacherNote: '' },
  ]
}

async function confirm() {
  if (!cur.value) return
  conf.value[idx.value] = true
  if (!cur.value.teacherNote) {
    cur.value.teacherNote = '老师已确认'
  }
  // Call API to update diagnosis
  try {
    await diagnosesAPI.update(cur.value.id || ('diag_' + cur.value.num), {
      verdict: cur.value.verdict,
      ocrText: cur.value.ocrText,
      wrongStep: cur.value.wrongStep,
      errorCause: cur.value.errorCause,
      skillCause: cur.value.skillCause,
      kp: cur.value.kp,
      ability: cur.value.ability,
      teacherNote: cur.value.teacherNote,
      typical: cur.value.typical,
    })
  } catch {
    // ignore API error
  }
  idx.value = Math.min(idx.value + 1, diags.value.length - 1)
  appStore.showToast('本题已确认')
}

async function batchConfirm() {
  diags.value.forEach((d, i) => {
    if (d.confidence >= 0.6) {
      conf.value[i] = true
    }
  })
  const highConfIds = diags.value.filter(d => d.confidence >= 0.6).map(d => d.id || ('diag_' + d.num))
  try {
    await diagnosesAPI.batchConfirm({
      diagnosis_ids: highConfIds,
      min_confidence: 0.6,
    })
  } catch {
    // ignore
  }
  appStore.showToast('高置信度题目已批量确认')
}

onMounted(loadData)
</script>
