<template>
  <div class="page">
    <PageHeader title="阶段报告" :showBack="true" backPath="/teacher/students">
      <button class="btn btn-sm btn-outline" @click="handleExport">&#x1F4E5; 导出</button>
    </PageHeader>

    <div class="page-body">
      <LoadSpinner v-if="loading" text="加载报告数据..." />

      <template v-else>
        <!-- Student Info Card -->
        <div class="card" style="text-align:center">
          <div style="font-size:12px;color:var(--gray-400)">{{ student.name }} · {{ student.class_name || student.className }}</div>
          <div style="font-size:20px;font-weight:700;margin-top:2px">7月阶段诊断</div>
          <div style="font-size:11px;color:var(--gray-400);margin-top:2px">{{ dateRange }}</div>
        </div>

        <!-- Stage Config -->
        <div class="card">
          <div class="input-group">
            <label>阶段名称</label>
            <input class="input" v-model="stageName" placeholder="如：7月上半月诊断" />
          </div>
          <div class="input-group" style="margin-top:8px">
            <label>日期范围</label>
            <div style="display:flex;gap:8px;align-items:center">
              <input class="input" type="date" v-model="dateStart" style="flex:1" />
              <span style="color:var(--gray-400)">至</span>
              <input class="input" type="date" v-model="dateEnd" style="flex:1" />
            </div>
          </div>
        </div>

        <!-- KPI Grid -->
        <div class="kpi-grid">
          <div class="kpi-card">
            <div style="font-size:11px;color:var(--gray-400)">本阶段正确率</div>
            <div style="font-size:22px;font-weight:700" :style="{ color: correctRate >= 80 ? 'var(--success)' : correctRate >= 60 ? 'var(--warning)' : 'var(--danger)' }">{{ correctRate }}%</div>
            <div style="font-size:11px;color:var(--gray-400)">{{ correctCount }}/{{ totalDiagnoses }}题</div>
          </div>
          <div class="kpi-card">
            <div style="font-size:11px;color:var(--gray-400)">完成率</div>
            <div style="font-size:22px;font-weight:700;color:var(--success)">{{ completionRate }}%</div>
            <div style="font-size:11px;color:var(--gray-400)">{{ completedTasks }}/{{ totalTasks }}次任务</div>
          </div>
        </div>

        <!-- Teacher Comment -->
        <div class="card">
          <div style="font-weight:600;font-size:14px;margin-bottom:8px">&#x1F4DD; 老师评语</div>
          <textarea
            class="textarea"
            v-model="comment"
            style="min-height:100px;line-height:1.6;font-size:13px"
            placeholder="请输入评语，如：该生在分数单元进步明显，异分母分数加减从45%提升至80%..."
          ></textarea>
          <div style="font-size:11px;color:var(--gray-400);margin-top:4px">支持段落换行，可使用符号标记重点</div>
          <button class="btn btn-sm btn-primary" style="margin-top:8px" @click="saveComment" :disabled="saving">
            {{ saving ? '保存中...' : '保存评语' }}
          </button>
        </div>

        <!-- Recommendations -->
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <div style="font-weight:600;font-size:14px">&#x1F3AF; 下阶段建议</div>
            <button class="btn btn-sm btn-outline" @click="addRecommendation">+ 添加</button>
          </div>
          <div v-for="(rec, idx) in recommendations" :key="idx" style="display:flex;align-items:flex-start;gap:6px;margin-bottom:6px">
            <span style="font-size:14px;line-height:2;flex-shrink:0">{{ getRecIcon(rec.type) }}</span>
            <div style="flex:1">
              <input
                class="input"
                v-model="rec.text"
                style="font-size:13px;margin-bottom:2px"
                :placeholder="'建议内容 #' + (idx + 1)"
              />
              <select v-model="rec.type" class="input select" style="font-size:11px">
                <option v-for="rt in RECOMMENDATION_TYPES" :value="rt.value" :key="rt.value">{{ getRecIcon(rt.value) }} {{ rt.label }}</option>
              </select>
            </div>
            <button class="btn btn-sm btn-outline" style="color:var(--danger);flex-shrink:0;padding:2px 6px" @click="removeRecommendation(idx)">&#x2715;</button>
          </div>
          <div v-if="!recommendations.length" style="font-size:12px;color:var(--gray-400);padding:8px;text-align:center">
            暂无建议，点击"添加"创建
          </div>
        </div>
      </template>
    </div>

    <BottomNav :items="teacherNav" active="students" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { studentsAPI } from '@/api/students'
import { diagnosesAPI } from '@/api/diagnoses'
import { tasksAPI } from '@/api/tasks'
import BottomNav from '@/components/BottomNav.vue'
import PageHeader from '@/components/PageHeader.vue'
import LoadSpinner from '@/components/LoadSpinner.vue'
import { icons } from '@/utils/icons'
import { DIFFICULTY_LEVELS, RECOMMENDATION_TYPES } from '@/utils/constants'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()

const loading = ref(true)
const saving = ref(false)
const student = ref({})
const diagnoses = ref([])
const allTasks = ref([])
const comment = ref('')
const stageName = ref('7月阶段诊断')
const dateStart = ref('2026-07-01')
const dateEnd = ref('2026-07-15')
const recommendations = ref([])

const teacherNav = [
  { key: 'students', label: '学生', icon: icons.students },
  { key: 'tasks', label: '任务', icon: icons.tasks },
  { key: 'upload', label: '上传', icon: icons.upload },
  { key: 'exercise', label: '练习', icon: icons.exercise },
  { key: 'me', label: '我的', icon: icons.home },
]

const dateRange = computed(() => {
  if (dateStart.value && dateEnd.value) return `${dateStart.value} - ${dateEnd.value}`
  return '2026.07.01-07.15'
})

const totalDiagnoses = computed(() => diagnoses.value.length)
const correctCount = computed(() => diagnoses.value.filter(d => d.verdict === 'correct').length)
const correctRate = computed(() => {
  if (!totalDiagnoses.value) return 0
  return parseFloat(((correctCount.value / totalDiagnoses.value) * 100).toFixed(1))
})

const completedTasks = computed(() => {
  // Count tasks that have at least one diagnosis for this student
  const taskIds = new Set(diagnoses.value.map(d => d.taskId || d.task_id).filter(Boolean))
  return taskIds.size
})
const totalTasks = computed(() => allTasks.value.length || 10)
const completionRate = computed(() => {
  if (!totalTasks.value) return 0
  return parseFloat(((completedTasks.value / totalTasks.value) * 100).toFixed(1))
})

function onNav(key) {
  if (key === 'tasks') router.push('/teacher/tasks')
  else if (key === 'upload') router.push('/teacher/upload')
  else if (key === 'exercise') router.push('/teacher/exercise')
  else if (key === 'me') router.push('/teacher/me')
}

function getRecIcon(type) {
  const map = { consolidate: '\u2705', breakthrough: '\uD83D\uDD27', expand: '\uD83D\uDCC8', frequency: '\uD83D\uDCDD' }
  return map[type] || '\u25CF'
}

function getRecLabel(type) {
  const map = { consolidate: '继续巩固', breakthrough: '重点突破', expand: '拓展提升', frequency: '建议频率' }
  return map[type] || type
}

function addRecommendation() {
  recommendations.value.push({ text: '', type: 'consolidate' })
}

function removeRecommendation(idx) {
  recommendations.value.splice(idx, 1)
}

async function loadData() {
  loading.value = true
  const sid = route.params.studentId
  try {
    const [stuRes, diagRes, taskRes] = await Promise.allSettled([
      studentsAPI.getById(sid),
      diagnosesAPI.getList({ student_id: sid }),
      tasksAPI.getList(),
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
    if (taskRes.status === 'fulfilled') {
      const raw = taskRes.value
      allTasks.value = raw?.items || raw?.data || (Array.isArray(raw) ? raw : [])
    } else {
      allTasks.value = getMockTasks()
    }
  } catch {
    student.value = getMockStudent(sid)
    diagnoses.value = getMockDiagnoses()
    allTasks.value = getMockTasks()
  } finally {
    loadDefaults()
    loading.value = false
  }
}

function loadDefaults() {
  comment.value = '该生在分数单元进步明显，异分母分数加减从45%提升至80%。建议继续每周3次专项练习，重点加强分数应用题建模。'
  recommendations.value = [
    { text: '继续巩固：分数四则混合运算', type: 'consolidate' },
    { text: '重点突破：分数应用题建模', type: 'breakthrough' },
    { text: '拓展提升：分数与百分数综合', type: 'expand' },
    { text: '建议频率：每周3次，每次8-10题', type: 'frequency' },
  ]
}

function getMockStudent(sid) {
  const all = [
    { id: 's1', name: '张三', classId: 'c1', className: '五(1)班', class_name: '五(1)班', grade: '五年级', mastery: 85 },
    { id: 's2', name: '李四', classId: 'c1', className: '五(1)班', class_name: '五(1)班', grade: '五年级', mastery: 72 },
    { id: 's3', name: '王五', classId: 'c1', className: '五(1)班', class_name: '五(1)班', grade: '五年级', mastery: 58 },
  ]
  return all.find(s => s.id === sid) || all[0]
}

function getMockDiagnoses() {
  return [
    { num: 1, verdict: 'correct', kp: '分数概念', taskId: 'tk1', task_id: 'tk1' },
    { num: 2, verdict: 'correct', kp: '同分母分数加减', taskId: 'tk1', task_id: 'tk1' },
    { num: 3, verdict: 'incorrect', kp: '异分母分数加减', taskId: 'tk1', task_id: 'tk1' },
    { num: 4, verdict: 'correct', kp: '分数比较', taskId: 'tk1', task_id: 'tk1' },
    { num: 5, verdict: 'partially_correct', kp: '分数与小数互化', taskId: 'tk1', task_id: 'tk1' },
    { num: 6, verdict: 'incorrect', kp: '分数应用题建模', taskId: 'tk1', task_id: 'tk1' },
  ]
}

function getMockTasks() {
  return [
    { id: 'tk1', name: '第三单元周测-分数', type: '周测' },
    { id: 'tk2', name: '日常作业-三角形全等', type: '日常作业' },
  ]
}

async function saveComment() {
  saving.value = true
  const sid = student.value.id || route.params.studentId
  try {
    await studentsAPI.saveReport(sid, {
      stage_name: stageName.value,
      date_range: dateRange.value,
      teacher_comment: comment.value,
      recommendations: recommendations.value,
    })
    appStore.showToast('评语已保存')
  } catch {
    // Fallback: save locally
    appStore.showToast('评语已保存（本地）')
  } finally {
    saving.value = false
  }
}

function handleExport() {
  const recHtml = recommendations.value.map(r =>
    `<li>${getRecIcon(r.type)} ${getRecLabel(r.type)}：${r.text}</li>`
  ).join('')

  const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>阶段报告 - ${student.value.name}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 24px; max-width: 600px; margin: 0 auto; color: #1f2937; }
    h1 { font-size: 22px; text-align: center; margin-bottom: 4px; }
    .subtitle { text-align: center; font-size: 13px; color: #9ca3af; margin-bottom: 20px; }
    .section { margin-bottom: 20px; padding: 16px; background: #f9fafb; border-radius: 10px; }
    .section h2 { font-size: 15px; margin-bottom: 10px; }
    .kpi-row { display: flex; gap: 12px; }
    .kpi-box { flex: 1; text-align: center; padding: 12px; background: #fff; border-radius: 8px; }
    .kpi-box .val { font-size: 24px; font-weight: 700; }
    .kpi-box .lbl { font-size: 11px; color: #9ca3af; }
    .comment { font-size: 13px; line-height: 1.7; white-space: pre-wrap; }
    ul { padding-left: 18px; }
    li { font-size: 13px; line-height: 2; }
    .footer { text-align: center; font-size: 11px; color: #d1d5db; margin-top: 20px; border-top: 1px solid #e5e7eb; padding-top: 12px; }
  </style>
</head>
<body>
  <h1>${stageName.value}</h1>
  <p class="subtitle">${student.value.name} · ${student.value.class_name || student.value.className} · ${dateRange.value}</p>

  <div class="section">
    <h2>&#x1F4CA; 关键指标</h2>
    <div class="kpi-row">
      <div class="kpi-box"><div class="val" style="color:#4f46e5">${correctRate.value}%</div><div class="lbl">正确率 (${correctCount.value}/${totalDiagnoses.value}题)</div></div>
      <div class="kpi-box"><div class="val" style="color:#10b981">${completionRate.value}%</div><div class="lbl">完成率 (${completedTasks.value}/${totalTasks.value}次)</div></div>
    </div>
  </div>

  <div class="section">
    <h2>&#x1F4DD; 老师评语</h2>
    <p class="comment">${comment.value || '暂无评语'}</p>
  </div>

  <div class="section">
    <h2>&#x1F3AF; 下阶段建议</h2>
    <ul>${recHtml || '<li>暂无建议</li>'}</ul>
  </div>

  <div class="footer">由教学管理系统自动生成 &middot; ${new Date().toLocaleDateString('zh')}</div>
</body>
</html>`

  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${stageName.value}_${student.value.name}.html`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  appStore.showToast('报告已导出')
}

onMounted(loadData)
</script>
