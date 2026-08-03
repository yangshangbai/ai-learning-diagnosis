<template>
  <div class="page">
    <PageHeader title="AI助手">
      <template #actions>
        <button class="btn btn-sm btn-outline" @click="clearChat" style="font-size:11px">清空</button>
      </template>
    </PageHeader>

    <div class="page-body" style="display:flex;flex-direction:column;height:calc(100vh - 110px)">
      <!-- Capability Cards -->
      <div class="capability-bar">
        <div class="cap-card" v-for="c in capabilities" :key="c.label" @click="quickAsk(c.prompt)">
          <span>{{ c.icon }}</span>
          <span style="font-size:11px">{{ c.label }}</span>
        </div>
      </div>

      <!-- Chat Messages -->
      <div class="chat-area" ref="chatArea">
        <div v-if="messages.length === 0" class="welcome">
          <div style="font-size:40px">🤖</div>
          <h3>AI 智能助手</h3>
          <p style="font-size:13px;color:var(--gray-500);line-height:1.6;max-width:300px;margin:8px auto">
            我可以查询系统数据、分析教学情况、给出操作建议。<br/>
            试试点击下方的快捷问题，或直接输入你的问题。
          </p>
        </div>

        <div v-for="(m, i) in messages" :key="i" :class="'msg ' + m.role">
          <div class="msg-bubble" v-html="renderMarkdown(m.text)"></div>
          <div class="msg-time">{{ m.time }}</div>
        </div>
        <div v-if="thinking" class="msg assistant">
          <div class="msg-bubble thinking">思考中<span class="dots">...</span></div>
        </div>
      </div>

      <!-- Input Bar -->
      <div class="input-bar">
        <input
          class="input"
          v-model="input"
          placeholder="输入问题，如：查一下学生人数"
          @keyup.enter="send"
          :disabled="thinking"
        />
        <button class="btn btn-primary" @click="send" :disabled="!input.trim() || thinking">发送</button>
      </div>
    </div>

    <BottomNav :items="navItems" active="ai" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import BottomNav from '@/components/BottomNav.vue'
import { useAuthStore } from '@/stores/auth'
import { icons } from '@/utils/icons'
import request from '@/api/request'

const router = useRouter()
const authStore = useAuthStore()

const user = computed(() => authStore.user || JSON.parse(localStorage.getItem('user') || 'null'))
const role = computed(() => user.value?.role || 'research')

const input = ref('')
const thinking = ref(false)
const messages = ref([])
const chatArea = ref(null)

// ── AI Capabilities ──
const capabilities = [
  { icon: '📊', label: '学生人数', prompt: '查一下学生人数，以及各年级分布' },
  { icon: '👨‍🏫', label: '老师列表', prompt: '系统有哪些老师？各自负责什么？' },
  { icon: '📋', label: '任务状况', prompt: '任务总体情况怎么样？各状态有多少？' },
  { icon: '🎯', label: '薄弱点', prompt: '最近诊断中最薄弱的知识点有哪些？' },
  { icon: '📈', label: '掌握度', prompt: '各年级平均掌握度如何？' },
  { icon: '❓', label: '功能说明', prompt: '系统有哪些功能模块？怎么使用？' },
]

// ── Navigation ──
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

function onNav(key) {
  const map = {
    dashboard: '/admin/dashboard', org: '/admin/org',
    knowledge: '/admin/knowledge', qbank: '/admin/qbank', ai: '/admin/ai',
    diagnosis: '/admin/diagnosis', system: '/admin/system', me: '/admin/me'
  }
  if (map[key]) router.push(map[key])
}

// ── Chat Logic ──
function quickAsk(prompt) {
  input.value = prompt
  send()
}

async function loadHistory() {
  try {
    const res = await request.get('/ai/chat-history', { params: { page_size: 100 } })
    const items = res?.items || res?.data || (Array.isArray(res) ? res : [])
    if (items.length > 0) {
      messages.value = items.map(m => ({
        role: m.role,
        text: m.content,
        time: formatTime(m.created_at)
      }))
      await nextTick()
      scrollBottom()
    }
  } catch (e) {
    // No history or API unavailable, start fresh
  }
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0')
}

async function send() {
  const text = input.value.trim()
  if (!text || thinking.value) return
  input.value = ''
  addMessage('user', text)
  thinking.value = true

  try {
    const res = await request.post('/ai/assistant', { prompt: text })
    const reply = res?.reply || res?.data?.reply || '抱歉，AI暂未响应。'
    addMessage('assistant', reply)
  } catch (e) {
    addMessage('assistant', '⚠️ AI服务暂时不可用。')
  } finally {
    thinking.value = false
    await nextTick()
    scrollBottom()
  }
}

function addMessage(role, text) {
  const now = new Date()
  const time = now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0')
  messages.value.push({ role, text, time })
}

function clearChat() {
  messages.value = []
  request.delete('/ai/chat-history').catch(() => {})
}

function scrollBottom() {
  if (chatArea.value) {
    chatArea.value.scrollTop = chatArea.value.scrollHeight
  }
}

// Simple markdown: **bold**, newlines, emoji in text
function renderMarkdown(text) {
  if (!text) return ''
  let html = text
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    .replace(/\n/g, '<br/>')
    .replace(/📊|📋|👨‍🏫|🎯|📈|📚|🤖|⚠️|💡|📖/g, m => `<span style="font-size:16px">${m}</span>`)
  return html
}

onMounted(() => {
  loadHistory()
  scrollBottom()
})
</script>

<style scoped>
.capability-bar {
  display: flex; gap: 6px; overflow-x: auto; padding: 8px 0;
  flex-shrink: 0; -webkit-overflow-scrolling: touch;
}
.capability-bar::-webkit-scrollbar { display: none; }
.cap-card {
  display: flex; align-items: center; gap: 4px;
  padding: 6px 10px; border-radius: 16px;
  background: var(--primary-light); color: var(--primary);
  font-size: 12px; cursor: pointer; white-space: nowrap;
  border: 1px solid transparent; transition: all .2s;
  flex-shrink: 0;
}
.cap-card:hover { border-color: var(--primary); }
.chat-area {
  flex: 1; overflow-y: auto; padding: 8px 0;
}
.welcome {
  text-align: center; padding: 40px 20px;
}
.msg {
  margin-bottom: 12px; max-width: 85%;
}
.msg.user {
  margin-left: auto; text-align: right;
}
.msg.assistant {
  margin-right: auto;
}
.msg-bubble {
  display: inline-block; padding: 10px 14px; border-radius: 12px;
  font-size: 13px; line-height: 1.6; word-break: break-word;
}
.msg.user .msg-bubble {
  background: var(--primary); color: #fff; border-bottom-right-radius: 4px;
}
.msg.assistant .msg-bubble {
  background: var(--gray-100); color: var(--gray-800); border-bottom-left-radius: 4px;
}
.msg-bubble.thinking {
  background: var(--gray-100); color: var(--gray-500); font-style: italic;
}
.dots::after {
  content: ''; animation: dotPulse 1.5s steps(3, end) infinite;
}
@keyframes dotPulse {
  0% { content: '.'; } 33% { content: '..'; } 66% { content: '...'; } 100% { content: '.'; }
}
.msg-time {
  font-size: 10px; color: var(--gray-400); margin-top: 2px; padding: 0 4px;
}
.input-bar {
  display: flex; gap: 8px; padding: 8px 0;
  border-top: 1px solid var(--gray-200); flex-shrink: 0;
}
.input-bar .input {
  flex: 1; height: 44px; border: 1px solid var(--gray-200);
  border-radius: 22px; padding: 0 16px; font-size: 14px;
}
.input-bar .btn {
  height: 44px; border-radius: 22px; padding: 0 20px; font-size: 14px;
}
</style>
