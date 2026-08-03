<template>
  <div class="page">
    <PageHeader title="AI模型配置" :showBack="true" backPath="/admin/system" />

    <div class="page-body">
      <LoadSpinner v-if="loading" text="加载配置..." />

      <template v-else>
        <!-- Notice -->
        <div style="padding:11px 12px;background:var(--warning-light);border:1px solid #FDE68A;border-radius:8px;margin-bottom:12px;font-size:12px;color:var(--gray-700)">
          ⚠️ AppKey明文存储，仅超级管理员可查看和修改。切换AI模型后需保存生效。
        </div>

        <!-- Per-provider config cards -->
        <div v-for="(cfg, idx) in configs" :key="cfg.provider" class="card" style="margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
            <div style="display:flex;align-items:center;gap:8px">
              <span style="font-size:18px">{{ providerIcon(cfg.provider) }}</span>
              <div>
                <div style="font-weight:600;font-size:14px">{{ providerLabel(cfg.provider) }}</div>
                <div style="font-size:11px;color:var(--gray-400)">{{ cfg.description }}</div>
              </div>
            </div>
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer">
              <input type="radio" :value="cfg.provider" v-model="activeProvider" @change="onActiveChange" />
              <span style="font-size:12px" :style="{ color: activeProvider === cfg.provider ? 'var(--success)' : 'var(--gray-400)', fontWeight: activeProvider === cfg.provider ? 600 : 400 }">
                {{ activeProvider === cfg.provider ? '● 当前使用' : '○ 启用' }}
              </span>
            </label>
          </div>

          <div class="input-group">
            <label>模型名称</label>
            <input class="input" v-model="cfg.model_name" :placeholder="providerPlaceholder(cfg.provider)" />
          </div>

          <div class="input-group">
            <label>AppKey / API Key</label>
            <div style="position:relative">
              <input
                class="input"
                :type="showKeys[idx] ? 'text' : 'password'"
                v-model="cfg.api_key"
                :placeholder="cfg.provider === 'mock' ? 'Mock模式无需AppKey' : '请输入API密钥'"
                style="padding-right:44px;font-family:monospace;font-size:13px"
              />
              <button
                type="button"
                @click="showKeys[idx] = !showKeys[idx]"
                style="position:absolute;right:8px;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;font-size:16px;padding:4px"
                :title="showKeys[idx] ? '隐藏' : '显示'"
              >{{ showKeys[idx] ? '🙈' : '👁️' }}</button>
            </div>
            <div v-if="cfg.api_key && showKeys[idx]" style="margin-top:4px;padding:6px 10px;background:var(--gray-50);border-radius:4px;font-family:monospace;font-size:12px;word-break:break-all;color:var(--gray-700)">
              {{ cfg.api_key }}
            </div>
          </div>

          <div class="input-group">
            <label>API地址 (可选)</label>
            <input class="input" v-model="cfg.base_url" placeholder="如: https://api.openai.com/v1" />
          </div>

          <div class="input-group">
            <label>额外配置 (JSON, 可选)</label>
            <textarea class="input" v-model="cfg.settings_json" rows="2" placeholder='{"temperature": 0.7, "max_tokens": 2000}' style="height:auto;font-family:monospace;font-size:12px;resize:vertical"></textarea>
          </div>
        </div>

        <!-- Test Connection -->
        <div class="card" style="margin-bottom:10px">
          <div style="font-weight:600;font-size:14px;margin-bottom:8px">连接测试</div>
          <div style="display:flex;gap:8px">
            <select class="input select" v-model="testProvider" style="flex:1">
              <option v-for="c in configs" :key="c.provider" :value="c.provider">{{ providerLabel(c.provider) }}</option>
            </select>
            <button class="btn btn-outline btn-sm" @click="testConnection" :disabled="testing">
              {{ testing ? '测试中...' : '测试连接' }}
            </button>
          </div>
          <div v-if="testResult" style="margin-top:8px;padding:8px 12px;border-radius:6px;font-size:12px"
            :style="{ background: testResult.ok ? 'var(--success-light)' : '#FEE2E2', color: testResult.ok ? '#047857' : '#991B1B' }">
            {{ testResult.msg }}
          </div>
        </div>

        <!-- Actions -->
        <div style="display:flex;gap:8px;margin-bottom:16px">
          <button class="btn btn-primary btn-block" @click="saveConfig" :disabled="saving" style="flex:1">
            {{ saving ? '保存中...' : '💾 保存配置' }}
          </button>
          <button class="btn btn-outline btn-block" @click="loadConfig" :disabled="loading" style="flex:1">
            🔄 重新加载
          </button>
        </div>
      </template>
    </div>

    <BottomNav :items="navItems" active="system" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { aiConfigAPI } from '@/api/aiConfig'
import PageHeader from '@/components/PageHeader.vue'
import BottomNav from '@/components/BottomNav.vue'
import LoadSpinner from '@/components/LoadSpinner.vue'
import { icons } from '@/utils/icons'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()

const user = computed(() => authStore.user || JSON.parse(localStorage.getItem('user') || 'null'))
const role = computed(() => user.value?.role || 'super')

const loading = ref(true)
const saving = ref(false)
const testing = ref(false)
const configs = ref([])
const activeProvider = ref('mock')
const showKeys = ref([])
const testProvider = ref('mock')
const testResult = ref(null)

const navItems = [
  { key: 'dashboard', label: '总览', icon: icons.dashboard },
  { key: 'org', label: '组织', icon: icons.org },
  { key: 'system', label: '系统', icon: icons.settings },
  { key: 'diagnosis', label: '诊断', icon: icons.diagnosis },
  { key: 'me', label: '我的', icon: icons.home },
]

function providerLabel(p) {
  const map = {
    mock: 'Mock AI (本地模拟)',
    openai: 'OpenAI GPT-4o',
    claude: 'Anthropic Claude 3',
    paddle: '百度 PaddleOCR + 文心',
    zhipu: '智谱 GLM-4V',
    qwen: '通义千问 VL',
  }
  return map[p] || p
}

function providerIcon(p) {
  const map = {
    mock: '🧪',
    openai: '🤖',
    claude: '🎓',
    paddle: '🐼',
    zhipu: '🧠',
    qwen: '☁️',
  }
  return map[p] || '🔧'
}

function providerPlaceholder(p) {
  const map = {
    openai: 'gpt-4o',
    claude: 'claude-3-opus-20240229',
    paddle: 'PaddleOCR',
    zhipu: 'glm-4v',
    qwen: 'qwen-vl-max',
    mock: 'mock-ai',
  }
  return map[p] || '模型名称'
}

async function loadConfig() {
  loading.value = true
  try {
    const res = await aiConfigAPI.getConfig()
    const items = res.data?.items || res.items || res.data || res || []
    configs.value = items.map(c => ({ ...c, settings_json: typeof c.settings_json === 'string' ? c.settings_json : JSON.stringify(c.settings_json || {}, null, 2) }))
    showKeys.value = configs.value.map(() => false)
    const active = items.find(c => c.is_active)
    activeProvider.value = active ? active.provider : 'mock'
    testResult.value = null
  } catch {
    appStore.showToast('加载AI配置失败')
  } finally {
    loading.value = false
  }
}

function onActiveChange() {
  configs.value.forEach(c => {
    c.is_active = (c.provider === activeProvider.value)
  })
}

async function saveConfig() {
  saving.value = true
  try {
    // Normalize settings_json
    const payload = configs.value.map(c => {
      let sj = c.settings_json || '{}'
      if (typeof sj === 'string') {
        try { JSON.parse(sj) } catch { sj = '{}' }
      }
      return { ...c, settings_json: typeof sj === 'string' ? sj : JSON.stringify(sj) }
    })
    await aiConfigAPI.saveConfig(payload)
    appStore.showToast('AI配置已保存')
  } catch {
    appStore.showToast('保存失败')
  } finally {
    saving.value = false
  }
}

async function testConnection() {
  testing.value = true
  testResult.value = null
  // Simulate connection test (real implementation would call backend health check)
  await new Promise(r => setTimeout(r, 1200))
  const cfg = configs.value.find(c => c.provider === testProvider.value)
  if (!cfg || !cfg.api_key) {
    testResult.value = { ok: false, msg: `${providerLabel(testProvider.value)}: 未配置AppKey，请先填写API密钥` }
  } else if (cfg.provider === 'mock') {
    testResult.value = { ok: true, msg: 'Mock AI: 本地模拟模式无需连接，始终可用 ✓' }
  } else {
    // In production, would call backend to verify the key
    testResult.value = { ok: true, msg: `${providerLabel(testProvider.value)}: AppKey已配置 (${cfg.api_key.slice(0, 8)}...)，生产环境将进行实际连通性验证` }
  }
  testing.value = false
}

function onNav(key) {
  const map = {
    dashboard: '/admin/dashboard',
    org: '/admin/org',
    diagnosis: '/admin/diagnosis',
    system: '/admin/system',
    me: '/admin/me',
  }
  if (map[key]) router.push(map[key])
}

onMounted(() => loadConfig())
</script>

<style scoped>
.input-group {
  margin-bottom: 10px;
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
</style>
