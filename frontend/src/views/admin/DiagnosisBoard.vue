<template>
  <div class="page">
    <PageHeader title="教学诊断看板" />
    <div class="page-body">
      <!-- Filters -->
      <div style="display:flex;gap:6px;margin-bottom:10px">
        <select class="input select" v-model="gradeFilter" @change="fetchBoard" style="flex:1">
          <option v-for="g in grades" :value="g" :key="g">{{ g }}</option>
        </select>
        <select class="input select" v-model="subjectFilter" @change="fetchBoard" style="flex:1">
          <option v-for="s in subjects" :value="s" :key="s">{{ s }}</option>
        </select>
      </div>

      <!-- Loading -->
      <div v-if="loading" style="text-align:center;padding:40px 0">
        <LoadSpinner text="加载诊断数据..." />
      </div>

      <!-- Error -->
      <div v-else-if="error" style="text-align:center;color:var(--danger);padding:32px 16px">
        <div style="margin-bottom:8px">{{ error }}</div>
        <button class="btn btn-sm btn-outline" @click="fetchBoard">重试</button>
      </div>

      <template v-else>
        <!-- Stats Overview -->
        <div class="kpi-grid">
          <div class="kpi-card">
            <div class="kpi-label">诊断记录</div>
            <div class="kpi-value">{{ statsTotal }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">正确率</div>
            <div class="kpi-value" :style="{color: correctRate >= 60 ? 'var(--success)' : 'var(--danger)'}">{{ correctRate }}%</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">错误题数</div>
            <div class="kpi-value" style="color:var(--danger)">{{ statsIncorrect }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">典型错题</div>
            <div class="kpi-value" style="color:var(--warning)">{{ statsTypical }}</div>
          </div>
        </div>

        <!-- Heatmap: Student × Knowledge Point -->
        <div class="card">
          <div style="font-weight:600;font-size:14px;margin-bottom:4px">知识点 × 学生 掌握度热力图</div>
          <div style="font-size:11px;color:var(--gray-400);margin-bottom:8px">绿色=正确 黄色=部分正确 红色=错误 灰色=待确认</div>
          <div v-if="!hasData" style="text-align:center;color:var(--gray-400);padding:40px 0">暂无数据</div>
          <div ref="heatmap" style="height:260px" v-show="hasData"></div>
        </div>

        <!-- Bar Chart: Knowledge Point Error Rate -->
        <div class="card" style="margin-top:10px" v-if="hasData">
          <div style="font-weight:600;font-size:14px;margin-bottom:8px">知识点错误率排行</div>
          <div ref="barChart" style="height:220px"></div>
        </div>

        <!-- AI Suggestion -->
        <div v-if="aiSuggestion" class="card" style="background:var(--primary-light);border-color:var(--primary);margin-top:10px">
          <div style="font-weight:600;font-size:14px">AI教学建议</div>
          <div style="font-size:13px;color:var(--gray-600);margin-top:4px;line-height:1.6" v-html="renderMarkdown(aiSuggestion)"></div>
        </div>
      </template>
    </div>

    <BottomNav :items="navItems" active="diagnosis" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import BottomNav from '@/components/BottomNav.vue'
import LoadSpinner from '@/components/LoadSpinner.vue'
import { diagnosesAPI } from '@/api/diagnoses'
import { useAuthStore } from '@/stores/auth'
import { useReferenceStore } from '@/stores/reference'
import { icons } from '@/utils/icons'
import { safeChart, disposeChart } from '@/utils/echarts'
import { SUBJECTS } from '@/utils/constants'
import request from '@/api/request'

const router = useRouter()
const authStore = useAuthStore()
const refStore = useReferenceStore()

const user = computed(() => authStore.user || JSON.parse(localStorage.getItem('user') || 'null'))
const role = computed(() => user.value?.role || 'admin')

const loading = ref(false)
const error = ref('')
const gradeFilter = ref('')
const subjectFilter = ref('数学')
const aiSuggestion = ref('')
const hasData = ref(false)
const statsTotal = ref(0)
const statsIncorrect = ref(0)
const statsTypical = ref(0)
const correctRate = ref(0)

const heatmap = ref(null)
const barChart = ref(null)
let chartInstance = null
let barInstance = null

// API-driven grades from reference store
const grades = computed(() => refStore.gradeNames)
const subjects = SUBJECTS

const adminNav = [
  { key: 'dashboard', label: '总览', icon: icons.dashboard },
  { key: 'org', label: '组织', icon: icons.org },
  { key: 'tasks', label: '任务', icon: icons.tasks },
  { key: 'diagnosis', label: '诊断', icon: icons.diagnosis },
  { key: 'me', label: '我的', icon: icons.home },
]

const researchNav = [
  { key: 'knowledge', label: '知识库', icon: icons.knowledge },
  { key: 'qbank', label: '题库', icon: icons.qbank },
  { key: 'ai', label: 'AI', icon: icons.ai },
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

const navItems = computed(() => {
  if (role.value === 'research') return researchNav
  return role.value === 'super' ? superNav : adminNav
})

async function fetchBoard() {
  loading.value = true
  error.value = ''
  hasData.value = false
  try {
    const params = { grade: gradeFilter.value, subject: subjectFilter.value }
    const res = await diagnosesAPI.getBoard(params)
    const items = res?.items || res?.data || (Array.isArray(res) ? res : [])
    const stats = res?.stats || {}

    if (items.length === 0) { loading.value = false; return }

    // Stats
    statsTotal.value = items.length
    statsIncorrect.value = stats.incorrect || 0
    statsTypical.value = items.filter(d => d.is_typical).length
    const correct = stats.correct || 0
    const total = (stats.correct + stats.incorrect + (stats.partially_correct || 0) + (stats.uncertain || 0)) || items.length
    correctRate.value = parseFloat((correct / Math.max(total, 1) * 100).toFixed(1))

    // Build student×KP heatmap
    const studentMap = {}, kpMap = {}
    items.forEach(d => {
      const sid = d.student_id; if (!studentMap[sid]) studentMap[sid] = { id: sid, name: d.student_name || ('学生'+sid) }
      const kp = d.kp_name; if (kp && !kpMap[kp]) kpMap[kp] = { name: kp }
    })
    const students = Object.values(studentMap), kps = Object.values(kpMap)
    const rawData = []
    items.forEach(d => {
      const x = students.findIndex(s => s.id === d.student_id)
      const y = kps.findIndex(k => k.name === d.kp_name)
      if (x < 0 || y < 0) return
      const v = d.verdict === 'correct' ? 100 : d.verdict === 'partially_correct' ? 50 : d.verdict === 'incorrect' ? 0 : 25
      rawData.push([x, y, v])
    })

    // Build bar chart: KP error rate (only count "incorrect" as errors, not partial/uncertain)
    const kpStats = {}
    items.forEach(d => {
      const kp = d.kp_name; if (!kp) return
      if (!kpStats[kp]) kpStats[kp] = { total: 0, incorrect: 0 }
      kpStats[kp].total++
      if (d.verdict === 'incorrect') kpStats[kp].incorrect++
    })
    const kpEntries = Object.entries(kpStats).sort((a, b) => (b[1].incorrect / b[1].total) - (a[1].incorrect / a[1].total))

    if (students.length > 0 && kps.length > 0 && rawData.length > 0) {
      hasData.value = true
      await nextTick()
      drawHeatmap(students, kps, rawData)
      if (kpEntries.length > 0) drawBarChart(kpEntries)
    }

    // AI suggestion via API
    aiSuggestion.value = `正确率 **${parseFloat(correctRate.value)}%**（${correct}/${total}），共 **${kps.length}** 个知识点。`
    fetchAISuggestion(items)
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '加载失败'
  } finally { loading.value = false }
}

async function fetchAISuggestion(items) {
  try {
    const kps = [...new Set(items.map(d => d.kp_name).filter(Boolean))].slice(0, 5)
    const incorrectKps = [...new Set(items.filter(d => d.verdict === 'incorrect').map(d => d.kp_name))].slice(0, 3)
    const prompt = `年级${gradeFilter.value}学科${subjectFilter.value}，共${items.length}条诊断，涉及知识点：${kps.join('、')}。薄弱点：${incorrectKps.join('、') || '无'}。请给出50字以内的教学建议。`
    const res = await request.post('/ai/suggest', { prompt })
    const text = res?.suggestion || res?.data?.suggestion || ''
    if (text) aiSuggestion.value = text
  } catch { /* keep stats-based suggestion */ }
}

function drawHeatmap(stus, kps, rawData) {
  const el = heatmap.value; if (!el) return
  if (chartInstance) disposeChart(chartInstance)
  chartInstance = safeChart(el); if (!chartInstance) return
  const data = rawData.map(([x, y, v]) => [y, x, v || 50])
  chartInstance.setOption({
    tooltip: { formatter: (p) => `${stus[p.value[1]]?.name} · ${kps[p.value[0]]?.name}<br/>${p.value[2]>=90?'✓正确':p.value[2]>=40?'△部分正确':p.value[2]>0?'✗错误':'?待确认'}` },
    grid: { left: 100, right: 16, top: 8, bottom: 28 },
    xAxis: { type: 'category', data: stus.map(s => s.name), axisLabel: { fontSize: 10, rotate: 30 } },
    yAxis: { type: 'category', data: kps.map(k => k.name), axisLabel: { fontSize: 10 } },
    visualMap: { min: 0, max: 100, orient: 'horizontal', left: 'center', bottom: 0, inRange: { color: ['#EF4444', '#F59E0B', '#10B981'] } },
    series: [{ type: 'heatmap', data, label: { show: false } }]
  })
}

function drawBarChart(kpEntries) {
  const el = barChart.value; if (!el) return
  if (barInstance) disposeChart(barInstance)
  barInstance = safeChart(el); if (!barInstance) return
  const names = kpEntries.map(([name]) => name.length > 6 ? name.slice(0,6)+'...' : name)
  const rates = kpEntries.map(([, v]) => parseFloat((v.incorrect / Math.max(v.total, 1) * 100).toFixed(1)))
  barInstance.setOption({
    tooltip: { trigger: 'axis', formatter: (p) => `${kpEntries[p[0].dataIndex][0]}<br/>错误率: ${p[0].value}%` },
    grid: { left: 36, right: 16, top: 8, bottom: 20 },
    xAxis: { type: 'category', data: names, axisLabel: { fontSize: 9, rotate: 30 } },
    yAxis: { max: 100, axisLabel: { fontSize: 10 } },
    series: [{ type: 'bar', data: rates.map((v, i) => ({ value: v, itemStyle: { color: v > 60 ? '#EF4444' : v > 30 ? '#F59E0B' : '#10B981' } })) }]
  })
}

function renderMarkdown(text) {
  if (!text) return ''
  return text.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/\n/g, '<br/>')
}

function onNav(key) {
  const r = role.value
  if (r === 'admin' || r === 'super') {
    const map = {
      dashboard: '/admin/dashboard',
      org: '/admin/org',
      tasks: '/admin/tasks',
      diagnosis: '/admin/diagnosis',
      me: '/admin/me'
    }
    if (map[key]) router.push(map[key])
  } else {
    const map = {
      knowledge: '/admin/knowledge',
      qbank: '/admin/qbank',
      ai: '/admin/ai',
      diagnosis: '/admin/diagnosis',
      me: '/admin/me'
    }
    if (map[key]) router.push(map[key])
  }
}

onMounted(async () => {
  await refStore.fetchAll()
  if (grades.value.length > 0 && !gradeFilter.value) {
    gradeFilter.value = grades.value[0]
  }
  fetchBoard()
})

onBeforeUnmount(() => {
  if (chartInstance) disposeChart(chartInstance)
  if (barInstance) disposeChart(barInstance)
})
</script>

<style scoped>
.kpi-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 10px; }
.kpi-card { background: #fff; border-radius: var(--radius); padding: 12px; box-shadow: var(--shadow); text-align: center; }
.kpi-label { font-size: 10px; color: var(--gray-400); }
.kpi-value { font-size: 20px; font-weight: 700; }
.input { height: 40px; border: 1px solid var(--gray-200); border-radius: var(--radius-sm); padding: 0 12px; font-size: 14px; box-sizing: border-box; }
.select { appearance: auto; }
</style>
