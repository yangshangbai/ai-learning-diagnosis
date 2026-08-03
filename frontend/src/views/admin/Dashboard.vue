<template>
  <div class="page">
    <PageHeader title="数据总览">
      <template #actions>
        <span style="font-size:12px;color:var(--gray-400)">{{ user?.name || '' }}</span>
        <button class="btn btn-sm btn-outline" style="color:var(--danger);border-color:var(--danger);margin-left:6px" @click="logout">退出</button>
      </template>
    </PageHeader>
    <div class="page-body">
      <!-- KPI Cards -->
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">学生总数</div>
          <div class="kpi-value">{{ stats.student_count || 0 }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">老师数</div>
          <div class="kpi-value">{{ stats.teacher_count || 0 }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">任务总数</div>
          <div class="kpi-value">{{ stats.task_count || 0 }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">待确认</div>
          <div class="kpi-value" style="color:var(--warning)">{{ stats.pending || 0 }}</div>
        </div>
      </div>

      <!-- Chart - Knowledge Error Rate by Grade -->
      <div class="card">
        <div style="font-weight:600;font-size:14px;margin-bottom:8px">{{ '各年级知识点错误率' }}</div>
        <LoadSpinner v-if="chartLoading" text="加载图表..." />
        <div ref="barChart" style="height:240px" v-show="!chartLoading"></div>
      </div>

      <!-- Weaknesses TOP5 -->
      <div class="card">
        <div style="font-weight:600;font-size:14px;margin-bottom:8px">{{ '共同薄弱点 TOP5' }}</div>
        <LoadSpinner v-if="weaknessLoading" text="分析薄弱点..." />
        <div v-else-if="weaknesses.length === 0" style="text-align:center;color:var(--gray-400);padding:20px 0">
          暂无数据
        </div>
        <div v-for="(kp, i) in weaknesses" :key="i" style="display:flex;align-items:center;gap:8px;margin-bottom:5px">
          <span style="font-size:11px;width:20px;color:var(--gray-400)">#{{ i + 1 }}</span>
          <span style="font-size:13px;flex:1">{{ kp.n || kp.name || kp.label }}</span>
          <span style="font-size:13px;color:var(--danger);font-weight:600">{{ kp.r ?? kp.rate ?? kp.error_rate ?? 0 }}%</span>
          <div style="width:60px;height:5px;background:var(--gray-100);border-radius:3px">
            <div :style="{ width: (kp.r ?? kp.rate ?? kp.error_rate ?? 0) + '%', height: '100%', background: 'var(--danger)', borderRadius: '3px' }"></div>
          </div>
        </div>
      </div>
    </div>

    <BottomNav :items="navItems" active="dashboard" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import BottomNav from '@/components/BottomNav.vue'
import LoadSpinner from '@/components/LoadSpinner.vue'
import { dashboardAPI } from '@/api/dashboard'
import { knowledgeAPI } from '@/api/knowledge'
import { useAuthStore } from '@/stores/auth'
import { useReferenceStore } from '@/stores/reference'
import { icons } from '@/utils/icons'
import { safeChart, disposeChart } from '@/utils/echarts'
import { SUBJECTS } from '@/utils/constants'

const router = useRouter()
const authStore = useAuthStore()
const refStore = useReferenceStore()

const user = computed(() => authStore.user || JSON.parse(localStorage.getItem('user') || 'null'))
const role = computed(() => user.value?.role || 'admin')

const stats = ref({ student_count: 0, teacher_count: 0, task_count: 0, pending: 0, completion_rate: 0 })
const weaknesses = ref([])
const chartLoading = ref(true)
const weaknessLoading = ref(true)

const barChart = ref(null)
let chartInstance = null

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

function logout() {
  authStore.logout()
  router.push('/login')
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

function buildChartFromKnowledge(flatKps) {
  // Use API-driven grade order from reference store
  const gradeOrder = refStore.gradeNames.length > 0
    ? [...refStore.gradeNames]
    : ['五年级', '六年级', '初一', '初二', '初三']
  const subjects = SUBJECTS

  const gradeMap = {}
  gradeOrder.forEach(g => {
    gradeMap[g] = {}
    subjects.forEach(s => { gradeMap[g][s] = [] })
  })

  // Map API data: only leaf nodes with actual mastery data (>0 = has data)
  flatKps.forEach(kp => {
    const grade = kp.grade || kp.grade_name || ''
    const subject = kp.subject || kp.subject_name || ''
    const mastery = kp.mastery
    // Skip: no grade/subject, mastery=0 (means "no data", not "0% mastery"), or non-leaf nodes
    if (!grade || !subject || mastery === undefined || mastery === null || mastery === 0.0 || mastery === 0) return

    const errorRate = parseFloat((100 - mastery).toFixed(1))

    if (gradeMap[grade] && gradeMap[grade][subject] !== undefined) {
      gradeMap[grade][subject].push(errorRate)
    } else {
      for (const g of gradeOrder) {
        if (grade.includes(g) || g.includes(grade)) {
          for (const s of subjects) {
            if (subject.includes(s) || s.includes(subject)) {
              gradeMap[g][s].push(errorRate)
              return
            }
          }
        }
      }
    }
  })

  // Compute series: one per subject
  const series = subjects.map(subject => {
    const data = gradeOrder.map(grade => {
      const vals = gradeMap[grade][subject]
      return vals.length > 0 ? parseFloat((vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1)) : 0
    })
    const colors = { '数学': '#4F46E5', '物理': '#10B981', '化学': '#F59E0B' }
    return {
      name: subject,
      type: 'bar',
      data,
      itemStyle: { color: colors[subject] || '#4F46E5' }
    }
  }).filter(s => s.data.some(v => v > 0))

  return { grades: gradeOrder, series }
}

function drawChart(grades, series) {
  nextTick(() => {
    const el = barChart.value
    if (!el) return
    if (chartInstance) disposeChart(chartInstance)
    chartInstance = safeChart(el)
    if (!chartInstance) return

    const xData = grades
    const yMax = Math.max(...series.flatMap(s => s.data), 80)
    const yRounded = Math.ceil(yMax / 20) * 20 || 100

    chartInstance.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 40, right: 20, top: 8, bottom: 20 },
      xAxis: { type: 'category', data: xData },
      yAxis: { max: yRounded },
      series
    })
  })
}

function computeWeaknesses(flatKps) {
  // Only leaf nodes with actual mastery data (mastery > 0 = has data)
  return flatKps
    .filter(kp => kp.mastery > 0 && (kp.grade || kp.grade_name))
    .map(kp => ({
      n: kp.name || kp.label || kp.kp_name || '',
      r: parseFloat((100 - kp.mastery).toFixed(1))
    }))
    .filter(w => w.r > 0)  // exclude 0% error rate
    .sort((a, b) => b.r - a.r)
    .slice(0, 5)
}

async function fetchStats() {
  try {
    const res = await dashboardAPI.getStats()
    // Interceptor already unwrapped response.data, so res is the DashboardStats object
    const data = res?.data || res
    if (data) {
      // Map API snake_case fields to template camelCase expectations
      stats.value = {
        student_count: data.total_students || data.student_count || 0,
        teacher_count: data.total_teachers || data.teacher_count || 0,
        task_count: data.total_tasks || data.task_count || 0,
        pending: data.pending_review || data.pending || 0,
        completion_rate: data.completion_rate || 0,
      }
    }
    // Extract weaknesses from API response (now correctly unwrapped)
    const weaknessesData = data?.top_weaknesses
    if (weaknessesData && Array.isArray(weaknessesData) && weaknessesData.length > 0) {
      weaknesses.value = weaknessesData
        .map(w => ({
          n: w.kp_name || w.name || w.label || w.n || '',
          r: parseFloat(((w.correct_rate !== undefined ? (100 - w.correct_rate) : (w.rate || w.r || w.error_rate || 0))).toFixed(1))
        }))
        .filter(w => w.r > 0)  // exclude 0% error rate items
      weaknessLoading.value = false
    }

    // Build chart from grade_distribution (real data, not knowledge tree mastery)
    const gradeDist = data?.grade_distribution
    if (gradeDist && Array.isArray(gradeDist) && gradeDist.length > 0) {
      const filtered = gradeDist.filter(g => g.count > 0)
      const grades = filtered.map(g => g.grade)
      const masteryData = filtered.map(g => parseFloat((100 - g.mastery).toFixed(1)))
      if (grades.length > 0 && masteryData.some(v => v > 0)) {
        drawChart(grades, [
          { name: '错误率', type: 'bar', data: masteryData, itemStyle: { color: '#EF4444' } }
        ])
      }
    }
  } catch (e) {
    console.warn('Failed to fetch dashboard stats:', e)
  } finally {
    chartLoading.value = false
    if (weaknessLoading.value) weaknessLoading.value = false
  }
}

async function fetchChartData() {
  try {
    const res = await knowledgeAPI.getFlat({ flat: true })
    const flatKps = res?.items || res?.data || (Array.isArray(res) ? res : [])

    if (Array.isArray(flatKps) && flatKps.length > 0) {
      if (weaknesses.value.length === 0) {
        weaknesses.value = computeWeaknesses(flatKps)
        weaknessLoading.value = false
      }
    }
  } catch (e) {
    console.warn('Failed to fetch knowledge data:', e)
  } finally {
    if (weaknessLoading.value) weaknessLoading.value = false
  }
}

onMounted(async () => {
  await refStore.fetchAll()
  fetchStats()
  fetchChartData()
})

onBeforeUnmount(() => {
  if (chartInstance) disposeChart(chartInstance)
})
</script>

<style scoped>
.kpi-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 12px;
}
.kpi-card {
  background: #fff;
  border-radius: var(--radius);
  padding: 16px;
  box-shadow: var(--shadow);
}
.kpi-label {
  font-size: 11px;
  color: var(--gray-400);
}
.kpi-value {
  font-size: 22px;
  font-weight: 700;
}
</style>
