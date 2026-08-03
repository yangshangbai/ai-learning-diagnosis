<template>
  <div class="page">
    <PageHeader title="学生档案" :showBack="true" backPath="/teacher/students">
      <div style="display:flex;gap:6px">
        <button class="btn btn-sm btn-outline" @click="refreshData">&#x1F504;</button>
        <button class="btn btn-sm btn-outline" @click="handleShare">&#x1F4E4; 分享</button>
      </div>
    </PageHeader>

    <div class="page-body">
      <LoadSpinner v-if="loading" text="加载学生数据..." />

      <template v-else>
        <!-- Gradient Header Card -->
        <div class="card" style="background:linear-gradient(135deg,var(--primary),var(--primary-dark));color:#fff;border:none">
          <div style="display:flex;align-items:center;gap:12px">
            <div
              :style="{width:'52px',height:'52px',borderRadius:'50%',background:'rgba(255,255,255,.2)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:'22px',fontWeight:'700'}"
            >{{ (student.name || '?')[0] }}</div>
            <div style="flex:1">
              <div style="font-size:18px;font-weight:700">{{ student.name }}</div>
              <div style="font-size:12px;opacity:.8">学生编号 {{ String(student.id || '') }} · {{ student.class_name || student.className }} · {{ student.grade }}</div>
            </div>
            <div style="text-align:center">
              <div style="font-size:32px;font-weight:800">{{ computedMastery }}%</div>
              <div style="font-size:11px;opacity:.8">整体掌握度</div>
            </div>
          </div>
          <div style="margin-top:8px">
            <span v-for="w in computedWeakKps" :key="w" class="tag" style="background:rgba(255,255,255,.2);color:#fff;margin-right:4px">{{ w }}</span>
            <span v-if="!computedWeakKps.length" style="font-size:12px;opacity:.8">&#x1F389; 无薄弱知识点</span>
          </div>
        </div>

        <!-- Tabs -->
        <div style="display:flex;gap:4px;background:var(--gray-100);border-radius:8px;padding:3px;margin-bottom:12px">
          <button
            v-for="t in tabs"
            :key="t.k"
            @click="tab = t.k"
            style="flex:1;padding:7px;border:none;border-radius:6px;font-size:12px;cursor:pointer;font-weight:500"
            :style="{background: tab === t.k ? '#fff' : 'transparent', color: tab === t.k ? 'var(--primary)' : 'var(--gray-500)'}"
          >{{ t.l }}</button>
        </div>

        <!-- Tab: Trend -->
        <div v-if="tab === 'trend'" class="card fade-in">
          <div style="font-weight:600;font-size:14px;margin-bottom:10px">知识点掌握趋势</div>
          <div v-if="!trendSeries.length" style="text-align:center;padding:20px;color:var(--gray-400);font-size:13px">
            暂无历史快照数据，显示最近诊断数据
          </div>
          <div ref="trendChart" style="height:240px"></div>
        </div>

        <!-- Tab: Ability -->
        <div v-if="tab === 'ability'" class="card fade-in">
          <div style="font-weight:600;font-size:14px;margin-bottom:10px">能力雷达</div>
          <div ref="radarChart" style="height:280px"></div>
        </div>

        <!-- Tab: Errors -->
        <div v-if="tab === 'errors'" class="card fade-in">
          <div style="font-weight:600;font-size:14px;margin-bottom:10px">高频错因</div>
          <div v-if="!computedErrorCauses.length" style="text-align:center;padding:20px;color:var(--gray-400);font-size:13px">
            暂无诊断数据
          </div>
          <div v-for="e in computedErrorCauses" :key="e.c" style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
            <span style="font-size:12px;width:70px">{{ e.c }}</span>
            <div style="flex:1;height:16px;background:var(--gray-100);border-radius:8px;overflow:hidden">
              <div :style="{width: Math.min(e.pct, 100) + '%',height:'100%',background: e.cl,borderRadius:'8px',transition:'width .3s'}"></div>
            </div>
            <span style="font-size:12px;font-weight:600">{{ e.n }}次</span>
          </div>
        </div>

        <!-- Tab: Wrong Book -->
        <div v-if="tab === 'wrongbook'" class="card fade-in">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
            <div style="font-weight:600;font-size:14px">错题本</div>
            <span class="tag tag-red">复错优先</span>
          </div>
          <div v-for="d in wrongDiagnoses" :key="d.num || d.id" style="padding:10px 0;border-bottom:1px solid var(--gray-50)">
            <div style="display:flex;align-items:center;gap:6px">
              <span class="tag" :class="verdictTag(d.verdict)">第{{ d.num }}题</span>
              <b style="font-size:13px">{{ d.kp }}</b>
              <span v-if="d.typical" class="tag tag-yellow">典型错题</span>
            </div>
            <div style="font-size:12px;color:var(--gray-500);line-height:1.5;margin-top:4px">{{ d.wrongStep }} · {{ d.errorCause || d.skillCause }}</div>
            <div style="font-size:12px;color:var(--primary);margin-top:4px">建议：先重做原题，再做2道同知识点变式题</div>
          </div>
          <EmptyState v-if="!wrongDiagnoses.length" icon="&#x1F4DD;" title="暂无错题" desc="学生表现良好，暂无错题记录" />
        </div>

        <!-- Tab: Plans -->
        <div v-if="tab === 'plans'" class="card fade-in">
          <div style="font-weight:600;font-size:14px;margin-bottom:10px">练习计划追踪</div>
          <div v-for="p in studentPlans" :key="p.id" style="padding:10px 0;border-bottom:1px solid var(--gray-50)">
            <div style="display:flex;justify-content:space-between;gap:8px">
              <b style="font-size:13px">{{ p.targetKP || p.kp }}</b>
              <span class="tag" :class="((p.effect || '').includes('改善') || (p.effect || '').includes('提升')) ? 'tag-green' : 'tag-yellow'">{{ p.effect || '进行中' }}</span>
            </div>
            <div style="font-size:12px;color:var(--gray-500);margin-top:4px">{{ p.frequency || p.freq }} · {{ p.count }}题/次 · {{ p.difficulty }}</div>
          </div>
          <EmptyState v-if="!studentPlans.length" icon="&#x1F4DD;" title="暂无练习计划" desc="可根据薄弱知识点生成专项练习" />
        </div>

        <!-- Tab: History -->
        <div v-if="tab === 'history'" class="card fade-in">
          <div style="font-weight:600;font-size:14px;margin-bottom:10px">历史记录</div>
          <div v-for="t in historyTasks" :key="t.id" style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--gray-50)">
            <div>
              <div style="font-weight:500;font-size:14px">{{ t.name }}</div>
              <div style="font-size:11px;color:var(--gray-400)">{{ t.type }} · {{ t.createdAt || t.created_at }}</div>
            </div>
            <span class="tag" :class="t.status === 'pending_review' ? 'tag-yellow' : t.status === 'ai_processing' ? 'tag-primary' : 'tag-gray'">{{ statusLabel(t.status) }}</span>
          </div>
        </div>

        <!-- Fixed Bottom Bar -->
        <div style="position:fixed;bottom:72px;left:50%;transform:translateX(-50%);width:100%;max-width:420px;background:#fff;border-top:1px solid var(--gray-100);padding:8px 16px;display:flex;gap:8px;z-index:50">
          <button class="btn btn-primary btn-sm" style="flex:1" @click="router.push('/teacher/exercise')">&#x1F4DD; 生成练习</button>
          <button class="btn btn-outline btn-sm" style="flex:1" @click="router.push('/teacher/report/' + (student.id || route.params.id))">&#x1F4CA; 阶段报告</button>
        </div>
      </template>
    </div>

    <BottomNav :items="teacherNav" active="students" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { studentsAPI } from '@/api/students'
import { diagnosesAPI } from '@/api/diagnoses'
import { exercisesAPI } from '@/api/exercises'
import BottomNav from '@/components/BottomNav.vue'
import PageHeader from '@/components/PageHeader.vue'
import LoadSpinner from '@/components/LoadSpinner.vue'
import EmptyState from '@/components/EmptyState.vue'
import { icons } from '@/utils/icons'
import { verdictTag, statusLabel } from '@/utils/helpers'
import { safeChart, disposeChart } from '@/utils/echarts'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()

const loading = ref(true)
const student = ref({})
const diagnoses = ref([])
const plans = ref([])
const historyTasks = ref([])
const snapshots = ref([])
const tab = ref('trend')

const trendChart = ref(null)
const radarChart = ref(null)
let trendInstance = null
let radarInstance = null

const tabs = [
  { k: 'trend', l: '趋势' },
  { k: 'ability', l: '能力' },
  { k: 'errors', l: '错因' },
  { k: 'wrongbook', l: '错题' },
  { k: 'plans', l: '练习' },
  { k: 'history', l: '记录' },
]

const teacherNav = [
  { key: 'students', label: '学生', icon: icons.students },
  { key: 'tasks', label: '任务', icon: icons.tasks },
  { key: 'upload', label: '上传', icon: icons.upload },
  { key: 'exercise', label: '练习', icon: icons.exercise },
  { key: 'me', label: '我的', icon: icons.home },
]

// --- Computed data from real APIs ---

const studentPlans = computed(() => {
  return plans.value.filter(p => p.student_id === student.value.id || p.studentId === student.value.id)
})

const wrongDiagnoses = computed(() => {
  return diagnoses.value.filter(d => d.verdict !== 'correct').slice(0, 5)
})

const computedMastery = computed(() => {
  if (student.value.mastery) return student.value.mastery
  if (!diagnoses.value.length) return 0
  const correct = diagnoses.value.filter(d => d.verdict === 'correct').length
  return parseFloat(((correct / diagnoses.value.length) * 100).toFixed(1))
})

const computedWeakKps = computed(() => {
  if (student.value.weak?.length) return student.value.weak
  const kpMap = {}
  diagnoses.value.filter(d => d.verdict !== 'correct').forEach(d => {
    if (d.kp) kpMap[d.kp] = (kpMap[d.kp] || 0) + 1
  })
  return Object.entries(kpMap)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([kp]) => kp)
})

const computedErrorCauses = computed(() => {
  const causeMap = {}
  diagnoses.value.filter(d => d.errorCause).forEach(d => {
    causeMap[d.errorCause] = (causeMap[d.errorCause] || 0) + 1
  })
  // Also count skill_cause if no errorCause
  if (!Object.keys(causeMap).length) {
    diagnoses.value.filter(d => d.verdict !== 'correct').forEach(d => {
      const cause = d.errorCause || d.skillCause || '概念混淆'
      causeMap[cause] = (causeMap[cause] || 0) + 1
    })
  }
  if (!Object.keys(causeMap).length) return []
  const colors = ['#EF4444', '#F59E0B', '#8B5CF6', '#EC4899', '#3B82F6']
  const maxN = Math.max(...Object.values(causeMap), 1)
  return Object.entries(causeMap)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([c, n], i) => ({ c, n, cl: colors[i % colors.length], pct: parseFloat(((n / maxN) * 100).toFixed(1)) }))
})

// Trend series from snapshots
const trendSeries = computed(() => {
  if (!snapshots.value.length) return []
  // Parse kp_mastery_json from each snapshot
  const kpSeries = {}
  const dates = []
  snapshots.value.forEach(snap => {
    const d = snap.created_at || snap.createdAt || snap.date || ''
    dates.push(d.slice(0, 10) || d)
    let mastery = {}
    if (snap.kp_mastery_json) {
      try {
        mastery = typeof snap.kp_mastery_json === 'string'
          ? JSON.parse(snap.kp_mastery_json)
          : snap.kp_mastery_json
      } catch { mastery = {} }
    }
    Object.entries(mastery).forEach(([kp, val]) => {
      if (!kpSeries[kp]) kpSeries[kp] = []
      kpSeries[kp].push(Number(val) || 0)
    })
  })
  // Fill gaps
  Object.keys(kpSeries).forEach(kp => {
    while (kpSeries[kp].length < dates.length) kpSeries[kp].push(null)
  })
  return { dates, kpSeries }
})

// --- Load Data ---

async function loadData() {
  loading.value = true
  const sid = route.params.id
  try {
    const [stuRes, diagRes, exerRes, taskRes, snapRes] = await Promise.allSettled([
      studentsAPI.getById(sid),
      diagnosesAPI.getList({ student_id: sid }),
      exercisesAPI.getList({ student_id: sid }),
      studentsAPI.getTasks(sid),
      studentsAPI.getSnapshots(sid),
    ])

    if (stuRes.status === 'fulfilled') {
      student.value = stuRes.value.data || stuRes.value || {}
    } else {
      student.value = getMockStudent(sid)
    }
    if (diagRes.status === 'fulfilled') {
      const raw = diagRes.value
      diagnoses.value = raw?.items || raw?.data || (Array.isArray(raw) ? raw : [])
    } else {
      diagnoses.value = getMockDiagnoses()
    }
    if (exerRes.status === 'fulfilled') {
      const raw = exerRes.value
      plans.value = raw?.items || raw?.data || (Array.isArray(raw) ? raw : [])
    } else {
      plans.value = getMockPlans(sid)
    }
    if (taskRes.status === 'fulfilled') {
      const raw = taskRes.value
      historyTasks.value = (raw?.items || raw?.data || (Array.isArray(raw) ? raw : [])).slice(0, 5)
    } else {
      historyTasks.value = getMockTasks()
    }
    if (snapRes.status === 'fulfilled') {
      const raw = snapRes.value
      snapshots.value = raw?.items || raw?.data || (Array.isArray(raw) ? raw : [])
    } else {
      snapshots.value = []
    }
  } catch {
    student.value = getMockStudent(sid)
    diagnoses.value = getMockDiagnoses()
    plans.value = getMockPlans(sid)
    historyTasks.value = getMockTasks()
    snapshots.value = []
  } finally {
    loading.value = false
    nextTick(() => drawCharts())
  }
}

async function refreshData() {
  await loadData()
  appStore.showToast('数据已刷新')
}

// --- Mock Data Fallbacks ---

function getMockStudent(sid) {
  const all = [
    { id: 's1', name: '张三', classId: 'c1', className: '五(1)班', class_name: '五(1)班', grade: '五年级', mastery: 85, trend: 'up', weak: ['分数通分'] },
    { id: 's2', name: '李四', classId: 'c1', className: '五(1)班', class_name: '五(1)班', grade: '五年级', mastery: 72, trend: 'stable', weak: ['三角形面积'] },
    { id: 's3', name: '王五', classId: 'c1', className: '五(1)班', class_name: '五(1)班', grade: '五年级', mastery: 58, trend: 'down', weak: ['异分母分数加减', '分数应用题'] },
  ]
  return all.find(s => s.id === sid) || all[0]
}

function getMockDiagnoses() {
  return [
    { num: 1, verdict: 'correct', ocrText: '3/8 + 2/8 = 5/8', wrongStep: '无', kp: '分数概念', relatedKps: ['同分母分数加减'], errorCause: '', skillCause: '无', ability: '概念理解能力', aiExplain: '学生正确理解了分数基本概念', confidence: 0.95, typical: false },
    { num: 2, verdict: 'correct', ocrText: '7/9 - 2/9 = 5/9', wrongStep: '无', kp: '同分母分数加减', relatedKps: ['分数概念'], errorCause: '', skillCause: '无', ability: '运算能力', aiExplain: '同分母计算扎实', confidence: 0.93, typical: false },
    { num: 3, verdict: 'incorrect', ocrText: '1/3 + 1/2 = 2/5', wrongStep: '未先通分，直接分子分母分别相加', kp: '异分母分数加减', relatedKps: ['通分', '分数基本性质'], errorCause: '概念混淆', skillCause: '程序性知识错误', ability: '概念理解能力', aiExplain: '未通分直接相加。正确做法应先通分为2/6+3/6=5/6', confidence: 0.91, typical: true },
    { num: 4, verdict: 'correct', ocrText: '3/5 > 4/9', wrongStep: '无', kp: '分数比较', relatedKps: ['通分'], errorCause: '', skillCause: '无', ability: '逻辑推理能力', aiExplain: '分数大小比较方法正确', confidence: 0.94, typical: false },
    { num: 5, verdict: 'partially_correct', ocrText: '1/8 = 0.12', wrongStep: '小数换算末位漏写5', kp: '分数与小数互化', relatedKps: ['除法计算'], errorCause: '计算失误', skillCause: 'S型-计算细节错误', ability: '运算能力', aiExplain: '思路正确，1/8=0.125', confidence: 0.87, typical: false },
    { num: 6, verdict: 'incorrect', ocrText: '剩下部分直接乘总量', wrongStep: '遗漏题干中"剩下的"这一条件', kp: '分数应用题建模', relatedKps: ['单位1识别', '分数乘法'], errorCause: '建模失败', skillCause: '审题偏差', ability: '应用建模能力', aiExplain: '未能将实际问题转化为分数模型', confidence: 0.88, typical: true },
  ]
}

function getMockPlans(sid) {
  return [
    { id: 'p1', studentId: 's1', student_id: 's1', targetKP: '分数通分+分数应用', frequency: '每周3次', freq: '每周3次', count: 15, difficulty: '中等', effect: '改善中' },
    { id: 'p2', studentId: 's3', student_id: 's3', targetKP: '异分母分数加减', frequency: '每天1次', freq: '每天1次', count: 10, difficulty: '基础', effect: '待观察' },
  ].filter(p => p.studentId === sid || p.student_id === sid)
}

function getMockTasks() {
  return [
    { id: 'tk1', name: '第三单元周测-分数', type: '周测', subject: '数学', grade: '五年级', status: 'pending_review', createdAt: '07/15' },
    { id: 'tk2', name: '日常作业-三角形全等', type: '日常作业', subject: '数学', grade: '五年级', status: 'ai_processing', createdAt: '07/16' },
  ]
}

// --- Chart Drawing ---

function buildTrendOption() {
  const ts = trendSeries.value
  const abilities = ['运算能力', '概念理解', '逻辑推理', '几何直观', '应用建模', '审题能力', '表达规范']
  const abilityVals = computeAbilityDimensions()

  if (ts.dates && ts.dates.length && Object.keys(ts.kpSeries).length) {
    // Use real snapshot data
    const seriesArr = Object.entries(ts.kpSeries).map(([kp, data], i) => ({
      name: kp,
      type: 'line',
      data,
      smooth: true,
      symbol: 'circle',
      symbolSize: 4,
    }))
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: Object.keys(ts.kpSeries), bottom: 0, textStyle: { fontSize: 10 } },
      grid: { left: 36, right: 16, top: 12, bottom: 36 },
      xAxis: { type: 'category', data: ts.dates, axisLabel: { fontSize: 10 } },
      yAxis: { min: 0, max: 100, axisLabel: { fontSize: 10 } },
      series: seriesArr,
    }
  }

  // Fallback: use computed ability data over mock weeks
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: abilities.slice(0, 3), bottom: 0, textStyle: { fontSize: 10 } },
    grid: { left: 36, right: 16, top: 12, bottom: 36 },
    xAxis: { type: 'category', data: ['06/17', '06/24', '07/01', '07/08', '07/15'], axisLabel: { fontSize: 10 } },
    yAxis: { min: 50, max: 100, axisLabel: { fontSize: 10 } },
    series: [
      { name: abilities[0], type: 'line', data: [72, 74, 70, 75, abilityVals[0]?.v || 80], smooth: true, symbol: 'circle', symbolSize: 4 },
      { name: abilities[1], type: 'line', data: [80, 82, 78, 84, abilityVals[1]?.v || 85], smooth: true, symbol: 'circle', symbolSize: 4 },
      { name: abilities[2], type: 'line', data: [60, 62, 65, 70, abilityVals[2]?.v || 68], smooth: true, symbol: 'circle', symbolSize: 4 },
    ],
  }
}

function computeAbilityDimensions() {
  // Aggregate ability from diagnoses
  const dims = {
    '运算能力': { total: 0, count: 0 },
    '概念理解能力': { total: 0, count: 0 },
    '逻辑推理能力': { total: 0, count: 0 },
    '几何直观能力': { total: 0, count: 0 },
    '应用建模能力': { total: 0, count: 0 },
    '审题能力': { total: 0, count: 0 },
    '表达规范能力': { total: 0, count: 0 },
  }
  diagnoses.value.forEach(d => {
    const ability = d.ability
    if (ability && dims[ability]) {
      const score = d.verdict === 'correct' ? 90 : d.verdict === 'partially_correct' ? 65 : 40
      dims[ability].total += score
      dims[ability].count++
    }
    // Also count by verdict as proxy
    if (d.ability) {
      const ab = d.ability
      if (!dims[ab]) {
        dims[ab] = { total: 0, count: 0 }
      }
    }
  })
  const shortNames = {
    '运算能力': '运算能力',
    '概念理解能力': '概念理解',
    '逻辑推理能力': '逻辑推理',
    '几何直观能力': '几何直观',
    '应用建模能力': '应用建模',
    '审题能力': '审题能力',
    '表达规范能力': '表达规范',
  }
  const defaults = [
    { n: '运算能力', v: 88 },
    { n: '概念理解', v: 72 },
    { n: '逻辑推理', v: 68 },
    { n: '几何直观', v: 85 },
    { n: '应用建模', v: 65 },
    { n: '审题能力', v: 70 },
    { n: '表达规范', v: 78 },
  ]
  const result = defaults.map(def => {
    const dim = dims[def.n] || dims[def.n + '能力']
    if (dim && dim.count > 0) {
      return { n: def.n, v: Math.round(dim.total / dim.count) }
    }
    return def
  })
  return result
}

function buildRadarOption() {
  const d = computeAbilityDimensions()
  return {
    radar: {
      center: ['50%', '50%'],
      radius: '65%',
      indicator: d.map(x => ({ name: x.n, max: 100 })),
      axisName: { fontSize: 10 },
    },
    series: [{
      type: 'radar',
      data: [
        {
          value: d.map(x => x.v),
          name: '当前水平',
          areaStyle: { color: 'rgba(79,70,229,0.2)' },
          lineStyle: { color: '#4F46E5', width: 2 },
          itemStyle: { color: '#4F46E5' },
        },
        {
          value: d.map(() => 70),
          name: '班级均线',
          areaStyle: { color: 'rgba(156,163,175,0.08)' },
          lineStyle: { color: '#9CA3AF', width: 1, type: 'dashed' },
          itemStyle: { color: '#9CA3AF' },
          symbol: 'none',
        },
      ],
    }],
  }
}

function drawCharts() {
  nextTick(() => {
    // Trend chart
    if (trendChart.value) {
      if (trendInstance) disposeChart(trendInstance)
      trendInstance = safeChart(trendChart.value)
      if (trendInstance) {
        trendInstance.setOption(buildTrendOption())
      }
    }

    // Radar chart
    if (radarChart.value) {
      if (radarInstance) disposeChart(radarInstance)
      radarInstance = safeChart(radarChart.value)
      if (radarInstance) {
        radarInstance.setOption(buildRadarOption())
      }
    }
  })
}

function handleShare() {
  const kps = computedWeakKps.value.join('、') || '无'
  const mastery = computedMastery.value || 0
  const totalDiag = diagnoses.value.length
  const correctDiag = diagnoses.value.filter(d => d.verdict === 'correct').length

  const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>学生档案 - ${student.value.name}</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:20px;max-width:400px;margin:0 auto;color:#1f2937}
  .card{background:linear-gradient(135deg,#4f46e5,#4338ca);color:#fff;border-radius:14px;padding:20px;margin-bottom:16px}
  .name{font-size:20px;font-weight:700}.info{font-size:12px;opacity:.8;margin-top:4px}
  .mastery{text-align:center;margin-top:12px}
  .mastery .num{font-size:40px;font-weight:800}.mastery .lbl{font-size:12px;opacity:.8}
  .tags{margin-top:8px}.tag{display:inline-block;padding:2px 8px;background:rgba(255,255,255,.2);border-radius:10px;font-size:11px;margin:2px 3px 2px 0}
  .stats{background:#f9fafb;border-radius:10px;padding:14px;margin-bottom:10px}
  .stats h3{font-size:13px;margin-bottom:6px}
  .stat-row{display:flex;justify-content:space-between;font-size:12px;padding:4px 0;border-bottom:1px solid #e5e7eb}
  .stat-row:last-child{border:none}
  .footer{text-align:center;font-size:11px;color:#d1d5db;margin-top:16px}
</style></head>
<body>
  <div class="card">
    <div class="name">${(student.value.name || '?')[0]} ${student.value.name}</div>
    <div class="info">${student.value.class_name || student.value.className || ''} · ${student.value.grade || ''}</div>
    <div class="mastery"><div class="num">${mastery}%</div><div class="lbl">整体掌握度</div></div>
    <div class="tags">${kps.split('、').map(k => `<span class="tag">${k}</span>`).join('')}</div>
  </div>
  <div class="stats">
    <h3>&#x1F4CA; 关键数据</h3>
    <div class="stat-row"><span>诊断题目</span><b>${totalDiag}题</b></div>
    <div class="stat-row"><span>正确题数</span><b>${correctDiag}题</b></div>
	    <div class="stat-row"><span>正确率</span><b>${totalDiag ? parseFloat((correctDiag/totalDiag*100).toFixed(1)) : 0}%</b></div>
    <div class="stat-row"><span>薄弱知识点</span><b>${computedWeakKps.value.length}个</b></div>
  </div>
  <div class="footer">由教学管理系统生成 · ${new Date().toLocaleDateString('zh')}</div>
</body></html>`

  // Try clipboard API first, fallback to download
  if (navigator.clipboard && navigator.clipboard.write) {
    const blob = new Blob([html], { type: 'text/html' })
    const item = new ClipboardItem({ 'text/html': blob })
    navigator.clipboard.write([item]).then(() => {
      appStore.showToast('报告已复制到剪贴板')
    }).catch(() => {
      downloadShareHtml(html)
    })
  } else {
    downloadShareHtml(html)
  }
}

function downloadShareHtml(html) {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `学生档案_${student.value.name}.html`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  appStore.showToast('报告已下载')
}

function onNav(key) {
  const map = { students: '/teacher/students', tasks: '/teacher/tasks', upload: '/teacher/upload', exercise: '/teacher/exercise', me: '/teacher/me' }
  if (map[key]) router.push(map[key])
}

watch(tab, () => {
  if (tab.value === 'trend' || tab.value === 'ability') {
    nextTick(() => drawCharts())
  }
})

onMounted(loadData)

onBeforeUnmount(() => {
  if (trendInstance) disposeChart(trendInstance)
  if (radarInstance) disposeChart(radarInstance)
})
</script>
