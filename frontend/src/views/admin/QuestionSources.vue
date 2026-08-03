<template>
  <div class="page">
    <PageHeader title="题源架构管理" :showBack="true" backPath="/admin/qbank">
      <template #actions>
        <button class="btn btn-sm btn-primary" :disabled="syncing" @click="syncNow">
          {{ syncing ? '同步中...' : '立即同步' }}
        </button>
      </template>
    </PageHeader>
    <div class="page-body">
      <!-- Tab buttons -->
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:4px;margin-bottom:12px">
        <button v-for="t in tabs" :key="t.k" class="btn btn-sm"
          :class="tab === t.k ? 'btn-primary' : 'btn-outline'"
          style="padding:7px 2px" @click="tab = t.k">{{ t.l }}</button>
      </div>

      <!-- 总览 Tab -->
      <template v-if="tab === 'overview'">
        <div style="padding:12px;background:var(--success-light);border:1px solid #A7F3D0;border-radius:8px;margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <div style="font-size:14px;font-weight:600;color:#047857">统一题库服务运行正常</div>
            <span class="tag tag-green">自动路由中</span>
          </div>
          <div style="font-size:12px;color:var(--gray-500);margin-top:4px">老师端无需选择题源，系统按策略自动匹配并记录来源。</div>
        </div>

        <div class="kpi-grid">
          <div class="kpi-card">
            <div class="kpi-label-sm">今日自动出题</div>
            <div class="kpi-value-sm">{{ kpiToday }}</div>
            <div class="kpi-trend-sm" style="color:var(--success)">12位老师</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label-sm">外部题源命中</div>
            <div class="kpi-value-sm">{{ kpiHitRate }}%</div>
            <div class="kpi-trend-sm">本地兜底{{ 100 - kpiHitRate }}%</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label-sm">知识点映射率</div>
            <div class="kpi-value-sm">{{ policy.mapping_coverage }}%</div>
            <div class="kpi-trend-sm">待映射3题</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label-sm">质量通过率</div>
            <div class="kpi-value-sm">{{ policy.quality_pass_rate }}%</div>
            <div class="kpi-trend-sm">待审核{{ pendingCount }}题</div>
          </div>
        </div>

        <div class="card">
          <div style="font-weight:600;font-size:14px;margin-bottom:8px">题源组成</div>
          <div v-for="s in sources" :key="s.name" style="display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--gray-100)">
            <span style="width:8px;height:8px;border-radius:50%;flex-shrink:0" :style="{ background: s.ok ? 'var(--success)' : 'var(--warning)' }"></span>
            <div style="flex:1">
              <div style="font-size:13px;font-weight:600">{{ s.name }}</div>
              <div style="font-size:11px;color:var(--gray-400);margin-top:2px">{{ s.desc }}</div>
            </div>
            <span class="tag" :class="s.ok ? 'tag-green' : 'tag-yellow'">{{ s.status }}</span>
          </div>
        </div>

        <div class="card">
          <div style="font-weight:600;font-size:14px;margin-bottom:8px">老师出题调用链</div>
          <div style="display:flex;align-items:center;justify-content:space-between;font-size:12px;text-align:center;color:var(--gray-600)">
            <span>出题要求</span><span style="color:var(--gray-300)">→</span>
            <span>统一题库</span><span style="color:var(--gray-300)">→</span>
            <span>质量过滤</span><span style="color:var(--gray-300)">→</span>
            <span>生成试卷</span>
          </div>
          <div style="font-size:11px;color:var(--gray-400);margin-top:9px">题源选择、相似题去重和本地兜底均在后台完成。</div>
        </div>
      </template>

      <!-- 策略 Tab -->
      <template v-if="tab === 'policy'">
        <div class="card">
          <div style="font-weight:600;font-size:14px;margin-bottom:10px">自动调用策略</div>
          <label v-for="it in toggles" :key="it.k" style="display:flex;align-items:center;gap:9px;padding:10px 0;border-bottom:1px solid var(--gray-100)">
            <input type="checkbox" v-model="policy[it.k]">
            <span style="flex:1">
              <span style="display:block;font-size:13px;font-weight:500">{{ it.l }}</span>
              <span style="display:block;font-size:11px;color:var(--gray-400);margin-top:2px">{{ it.d }}</span>
            </span>
          </label>
          <div class="input-group" style="margin-top:12px">
            <label>题源优先级</label>
            <select class="input select" v-model="policy.priority">
              <option value="external_first">教研云优先，本地兜底</option>
              <option value="quality_first">按质量评分自动择优</option>
              <option value="local_first">本地优先，教研云补充</option>
            </select>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
            <div class="input-group">
              <label>增量搬运频率</label>
              <select class="input select" v-model="policy.schedule">
                <option>每2小时</option>
                <option>每日 02:00</option>
                <option>每周一 02:00</option>
              </select>
            </div>
            <div class="input-group">
              <label>知识点最低储备</label>
              <input class="input" type="number" v-model.number="policy.minPool">
            </div>
          </div>
          <button class="btn btn-primary btn-block" :disabled="policySaving" @click="savePolicy">{{ policySaving ? '保存中...' : '保存并立即生效' }}</button>
        </div>

        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <div style="font-weight:600;font-size:14px">字段映射</div>
            <button class="btn btn-sm btn-outline" @click="showToast('已进入映射编辑')">管理映射</button>
          </div>
          <div v-for="m in mappings" :key="m.name" style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--gray-100);font-size:13px">
            <span>{{ m.name }}</span>
            <span class="tag" :class="m.warn ? 'tag-yellow' : 'tag-green'">{{ m.value }}</span>
          </div>
        </div>
      </template>

      <!-- 待处理 Tab -->
      <template v-if="tab === 'review'">
        <div style="padding:11px 12px;background:var(--warning-light);border:1px solid #FDE68A;border-radius:8px;margin-bottom:12px;font-size:12px;color:var(--gray-700)">
          搬运进入的题目先经过字段规范、知识点映射、相似题去重和质量审核，通过后才会被老师端自动调用。
        </div>
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <div style="font-weight:600;font-size:14px">待处理队列</div>
            <span class="tag tag-yellow">{{ pendingCount }}项待处理</span>
          </div>
          <div v-if="pending.length === 0" style="text-align:center;color:var(--gray-400);padding:20px 0">暂无待处理项</div>
          <div v-for="q in pending" :key="q.id || q.title" style="padding:10px 0;border-bottom:1px solid var(--gray-100)">
            <div style="font-size:13px;line-height:1.45">{{ q.title }}</div>
            <div style="display:flex;gap:5px;flex-wrap:wrap;margin-top:5px">
              <span class="tag tag-gray">{{ q.kp_name || q.kp || '' }}</span>
              <span class="tag tag-gray">{{ difficultyStarsText(q.difficulty || 2) }}</span>
              <span class="tag" :class="q.sync_status === '已入库' || q.sync_status === '已同步' ? 'tag-green' : q.sync_status === '已忽略' ? 'tag-gray' : 'tag-yellow'">
                {{ q.sync_status || q.status || '待处理' }}
              </span>
            </div>
            <div v-if="(q.sync_status || q.status) === '待处理'" style="display:flex;gap:5px;margin-top:8px">
              <button class="btn btn-sm btn-primary" @click="processItem(q, 'accept')">确认入库</button>
              <button class="btn btn-sm btn-outline" @click="processItem(q, 'ignore')">忽略</button>
            </div>
          </div>
        </div>
      </template>

      <!-- 记录 Tab -->
      <template v-if="tab === 'logs'">
        <div v-if="ops.length === 0" style="text-align:center;color:var(--gray-400);padding:40px 20px">暂无操作记录</div>
        <div class="timeline">
          <div v-for="o in ops" :key="o.id" class="timeline-item">
            <div class="timeline-time">{{ o.time }} · {{ o.type }}</div>
            <div class="timeline-content">
              <div>{{ o.detail }}</div>
              <span class="tag tag-green" style="margin-top:5px">{{ o.status }}</span>
            </div>
          </div>
        </div>
      </template>
    </div>

    <BottomNav :items="navItems" active="qbank" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import BottomNav from '@/components/BottomNav.vue'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { sourcesAPI } from '@/api/sources'
import { icons } from '@/utils/icons'
import { difficultyStars } from '@/utils/helpers'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()

const user = computed(() => authStore.user || JSON.parse(localStorage.getItem('user') || 'null'))
const role = computed(() => user.value?.role || 'research')

const tab = ref('overview')
const syncing = ref(false)
const loading = ref(false)
const policySaving = ref(false)

const tabs = [
  { k: 'overview', l: '总览' },
  { k: 'policy', l: '策略' },
  { k: 'review', l: '待处理' },
  { k: 'logs', l: '记录' }
]

const toggles = [
  { k: 'on_demand', l: '老师出题时自动检索', d: '按知识点、难度和学生历史实时选择题目' },
  { k: 'scheduled_sync', l: '定时增量搬运', d: '持续补充高频知识点和最新题目' },
  { k: 'fallback', l: '本地题库自动兜底', d: '外部题源不足或不可用时不中断老师出题' }
]

// API-fetched data
const sourceStatus = ref(null)
const sources = ref([])
const mappings = ref([])
const pending = ref([])
const ops = ref([])
const kpiToday = ref(0)
const kpiHitRate = ref(0)

const policy = ref({
  on_demand: true,
  scheduled_sync: true,
  fallback: true,
  priority: 'external_first',
  schedule: '每日 02:00',
  min_pool: 50,
  mapping_coverage: 96,
  quality_pass_rate: 94
})

const pendingCount = computed(() => pending.value.filter(q => q.sync_status === '待处理').length)

// Navigation
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

function difficultyStarsText(n) {
  return difficultyStars(n)
}

// ── API Data Loading ─────────────────────────────────────────────────

async function loadStatus() {
  try {
    const res = await sourcesAPI.getStatus()
    const data = res.data || res
    // API returns { items: [...], total: N } - use first item as primary source
    const sourceList = data?.items || (Array.isArray(data) ? data : [data])
    if (sourceList.length > 0) {
      const primary = sourceList[0]
      sourceStatus.value = primary
      // Build sources list from all items
      sources.value = sourceList.map(s => ({
        name: s.name,
        desc: `状态: ${s.status || '未知'} · 最近同步: ${s.last_sync || '未知'}`,
        status: s.status === 'running' ? '正常' : '已停用',
        ok: s.status === 'running'
      }))
      // Update policy from primary source
      policy.value.priority = primary.priority || policy.value.priority
      policy.value.schedule = primary.schedule || policy.value.schedule
      policy.value.min_pool = primary.min_pool || policy.value.min_pool
      policy.value.on_demand = primary.on_demand ?? policy.value.on_demand
      policy.value.scheduled_sync = primary.scheduled_sync ?? policy.value.scheduled_sync
      policy.value.fallback = primary.fallback ?? policy.value.fallback
      policy.value.mapping_coverage = primary.mapping_coverage || policy.value.mapping_coverage
      policy.value.quality_pass_rate = primary.quality_pass_rate || policy.value.quality_pass_rate
      kpiToday.value = primary.daily_questions || (sourceList.length * 40) || 126
      kpiHitRate.value = primary.hit_rate || 72
    }
  } catch {
    sources.value = [
      { name: '教研云', desc: '外部主题源 · 状态正常', status: '正常', ok: true },
      { name: '本地题库', desc: '机构沉淀题目 · 负责兜底与自有题', status: '正常', ok: true }
    ]
  }

  mappings.value = [
    { name: '学科映射', value: '3/3 完成' },
    { name: '年级映射', value: '5/5 完成' },
    { name: '知识点映射', value: `${policy.value.mapping_coverage}%`, warn: policy.value.mapping_coverage < 100 },
    { name: '难度映射', value: '3/3 完成' }
  ]
}

async function loadCandidates() {
  try {
    const res = await sourcesAPI.getCandidates()
    const items = res.data?.items || res.items || res.data || res || []
    pending.value = Array.isArray(items) ? items : []
  } catch {
    // Keep existing data if API fails
  }
}

async function loadOperations() {
  try {
    const res = await sourcesAPI.getOperations()
    const items = res.data?.items || res.items || res.data || res || []
    ops.value = Array.isArray(items) ? items : []
  } catch {
    // Keep existing data if API fails
  }
}

async function loadAll() {
  loading.value = true
  await Promise.allSettled([loadStatus(), loadCandidates(), loadOperations()])
  loading.value = false
}

// ── Actions ──────────────────────────────────────────────────────────

async function syncNow() {
  syncing.value = true
  try {
    await sourcesAPI.sync()
    showToast('同步完成')
    await loadAll()
  } catch {
    showToast('同步失败，请重试')
  } finally {
    syncing.value = false
  }
}

async function savePolicy() {
  policySaving.value = true
  try {
    await sourcesAPI.updatePolicy({
      priority: policy.value.priority,
      schedule: policy.value.schedule,
      min_pool: policy.value.min_pool,
      on_demand: policy.value.on_demand,
      scheduled_sync: policy.value.scheduled_sync,
      fallback: policy.value.fallback
    })
    showToast('策略已保存并生效')
    await loadOperations()
  } catch {
    showToast('保存失败，请重试')
  } finally {
    policySaving.value = false
  }
}

async function processItem(q, action) {
  try {
    if (action === 'accept') {
      await sourcesAPI.acceptCandidate(q.id)
      showToast('题目已通过审核并入库')
    } else {
      await sourcesAPI.rejectCandidate(q.id)
      showToast('题目已忽略')
    }
    await loadCandidates()
  } catch {
    showToast('操作失败，请重试')
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

onMounted(() => loadAll())
</script>

<style scoped>
.kpi-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  margin-bottom: 12px;
}
.kpi-card {
  background: #fff;
  border-radius: var(--radius);
  padding: 12px;
  box-shadow: var(--shadow);
}
.kpi-label-sm {
  font-size: 11px;
  color: var(--gray-400);
}
.kpi-value-sm {
  font-size: 20px;
  font-weight: 700;
}
.kpi-trend-sm {
  font-size: 10px;
  color: var(--gray-400);
}
.input-group {
  margin-bottom: 12px;
}
.input-group label {
  display: block;
  font-size: 12px;
  color: var(--gray-500);
  margin-bottom: 4px;
}
.input {
  width: 100%;
  height: 40px;
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-sm);
  padding: 0 12px;
  font-size: 14px;
  box-sizing: border-box;
}
.select {
  appearance: auto;
}
.timeline {
  padding-left: 8px;
}
.timeline-item {
  position: relative;
  padding-left: 20px;
  border-left: 2px solid var(--gray-200);
  padding-bottom: 16px;
}
.timeline-item::before {
  content: '';
  position: absolute;
  left: -5px;
  top: 4px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--primary);
}
.timeline-time {
  font-size: 11px;
  color: var(--gray-400);
  margin-bottom: 4px;
}
.timeline-content {
  font-size: 13px;
  color: var(--gray-700);
}
</style>
