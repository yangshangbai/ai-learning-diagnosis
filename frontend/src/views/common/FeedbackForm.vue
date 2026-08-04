<template>
  <div class="page feedback-form-page">
    <PageHeader :title="pageTitle" showBack />

    <LoadSpinner v-if="loading" />

    <div v-else class="form-body">
      <!-- 标题 -->
      <label class="field-label">标题 <span class="required">*</span> <span class="char-count">{{ title.length }}/20</span></label>
      <input
        v-model="title"
        class="field-input"
        :maxlength="20"
        placeholder="请输入标题（20字以内）"
        :disabled="readonly"
      />

      <!-- 图片区 -->
      <label class="field-label">图片 <span class="optional">(选填)</span></label>
      <div class="images-row">
        <div v-for="(img, i) in images" :key="i" class="img-thumb" @click="previewIndex = i">
          <img :src="imgUrl(img)" />
          <button v-if="!readonly" class="img-remove" @click.stop="images.splice(i, 1)">×</button>
        </div>
        <button v-if="!readonly" class="add-img-btn" @click="$refs.fileInput.click()">
          + 添加图片
        </button>
        <input ref="fileInput" type="file" accept="image/*" hidden @change="onFileChange" />
      </div>

      <!-- 图片预览弹窗 -->
      <CrudModal v-if="previewIndex !== null" title="图片预览" @close="previewIndex = null" hideSave>
        <img :src="imgUrl(images[previewIndex])" style="max-width:100%;max-height:70vh;" />
      </CrudModal>

      <!-- 内容 -->
      <label class="field-label">内容 <span class="required">*</span> <span class="char-count">{{ content.length }}/200</span></label>
      <textarea
        v-model="content"
        class="field-textarea"
        :maxlength="200"
        rows="6"
        placeholder="请详细描述您的修改意见或BUG（200字以内）"
        :disabled="readonly"
      ></textarea>

      <!-- 提交按钮 -->
      <button v-if="!readonly" class="btn btn-primary btn-block" @click="doSubmit" :disabled="submitting">
        {{ submitting ? '提交中...' : '提交' }}
      </button>

      <!-- 管理员操作 -->
      <div v-if="isAdmin && feedback && feedback.status !== '已完成'" class="admin-actions">
        <button v-if="feedback.status === '已提交'" class="btn btn-outline" @click="doAccept">受理</button>
        <button v-if="feedback.status === '已受理'" class="btn btn-primary" @click="doComplete">标记完成</button>
      </div>

      <!-- 时间线 -->
      <div class="timeline">
        <div class="tl-item">提交时间：{{ formatTime(feedback?.submitted_at) }}</div>
        <div class="tl-item">受理时间：{{ formatTime(feedback?.accepted_at) }}</div>
        <div class="tl-item">完成时间：{{ formatTime(feedback?.completed_at) }}</div>
      </div>
    </div>

    <BottomNav :items="navItems" active="" @nav="onNav" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { feedbackAPI } from '@/api/feedback'
import PageHeader from '@/components/PageHeader.vue'
import LoadSpinner from '@/components/LoadSpinner.vue'
import CrudModal from '@/components/CrudModal.vue'
import BottomNav from '@/components/BottomNav.vue'
import { icons } from '@/utils/icons'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const navItems = computed(() => {
  const role = auth.user?.role
  if (role === 'teacher') return [
    { key: 'students', label: '学生', icon: icons.students },
    { key: 'tasks', label: '任务', icon: icons.tasks },
    { key: 'upload', label: '上传', icon: icons.upload },
    { key: 'exercise', label: '练习', icon: icons.exercise },
    { key: 'me', label: '我的', icon: icons.home },
  ]
  if (role === 'research') return [
    { key: 'knowledge', label: '知识库', icon: icons.knowledge },
    { key: 'qbank', label: '题库', icon: icons.qbank },
    { key: 'ai', label: 'AI', icon: icons.ai },
    { key: 'diagnosis', label: '诊断', icon: icons.diagnosis },
    { key: 'me', label: '我的', icon: icons.home },
  ]
  return [
    { key: 'dashboard', label: '总览', icon: icons.dashboard },
    { key: 'org', label: '组织', icon: icons.org },
    { key: 'tasks', label: '任务', icon: icons.tasks },
    { key: 'diagnosis', label: '诊断', icon: icons.diagnosis },
    { key: 'me', label: '我的', icon: icons.home },
  ]
})

function onNav(key) {
  const role = auth.user?.role
  if (role === 'teacher') {
    if (key === 'students') router.push('/teacher/students')
    else if (key === 'tasks') router.push('/teacher/tasks')
    else if (key === 'upload') router.push('/teacher/upload')
    else if (key === 'exercise') router.push('/teacher/exercise')
    else if (key === 'me') router.push('/teacher/me')
  } else if (role === 'research') {
    if (key === 'knowledge') router.push('/admin/knowledge')
    else if (key === 'qbank') router.push('/admin/qbank')
    else if (key === 'ai') router.push('/admin/ai')
    else if (key === 'diagnosis') router.push('/admin/diagnosis')
    else if (key === 'me') router.push('/admin/me')
  } else {
    if (key === 'dashboard') router.push('/admin/dashboard')
    else if (key === 'org') router.push('/admin/org')
    else if (key === 'tasks') router.push('/admin/tasks')
    else if (key === 'diagnosis') router.push('/admin/diagnosis')
    else if (key === 'me') router.push('/admin/me')
  }
}

const feedbackId = computed(() => route.params.id)
const isEdit = computed(() => route.path.includes('/edit'))
const isCreate = computed(() => route.path.includes('/create'))
const readonly = computed(() => !isEdit.value && !isCreate.value)
const isAdmin = computed(() => auth.user?.role === 'admin' || auth.user?.role === 'super')

const pageTitle = computed(() => {
  if (isCreate.value) return '提交反馈'
  if (isEdit.value) return '编辑反馈'
  return '反馈详情'
})

const feedback = ref(null)
const title = ref('')
const content = ref('')
const images = ref([])
const loading = ref(false)
const submitting = ref(false)
const previewIndex = ref(null)

function formatTime(t) {
  if (!t) return '-'
  const d = new Date(t)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function imgUrl(img) {
  if (!img) return ''
  if (img.startsWith('http') || img.startsWith('/api/')) return img
  // If it's a filename only, construct the full URL
  return `/api/feedback/preview/${img.split('/').pop()}`
}

async function loadFeedback() {
  if (isCreate.value) return
  loading.value = true
  try {
    const res = await feedbackAPI.getById(feedbackId.value)
    const data = res?.data || res
    feedback.value = data
    title.value = data.title || ''
    content.value = data.content || ''
    images.value = [...(data.images || [])]
  } catch { alert('加载失败') }
  finally { loading.value = false }
}

async function onFileChange(e) {
  const file = e.target.files?.[0]
  if (!file) return
  try {
    const res = await feedbackAPI.uploadImage(file)
    const data = res?.data || res
    images.value.push(data.url || data.filename)
  } catch { alert('图片上传失败') }
  e.target.value = ''
}

async function doSubmit() {
  if (!title.value.trim()) return alert('请输入标题')
  if (!content.value.trim()) return alert('请输入内容')
  if (title.value.length > 20) return alert('标题不能超过20字')
  if (content.value.length > 200) return alert('内容不能超过200字')

  submitting.value = true
  try {
    const payload = {
      title: title.value.trim(),
      content: content.value.trim(),
      images: images.value,
    }
    if (isEdit.value) {
      await feedbackAPI.update(feedbackId.value, payload)
    } else {
      await feedbackAPI.create(payload)
    }
    router.push('/feedback')
  } catch (e) {
    const msg = e?.response?.data?.detail || '提交失败'
    alert(msg)
  }
  finally { submitting.value = false }
}

async function doAccept() {
  try { await feedbackAPI.accept(feedbackId.value); router.push('/feedback') }
  catch { alert('受理失败') }
}

async function doComplete() {
  try { await feedbackAPI.complete(feedbackId.value); router.push('/feedback') }
  catch { alert('操作失败') }
}

onMounted(loadFeedback)
</script>

<style scoped>
.feedback-form-page { padding: 16px; max-width: 800px; margin: 0 auto; }
.form-body { background: #fff; border-radius: 12px; padding: 20px; }
.field-label { display: block; font-size: 14px; font-weight: 600; margin: 12px 0 6px; }
.char-count { font-weight: 400; color: #999; font-size: 12px; }
.required { color: #e74c3c; }
.optional { color: #999; font-weight: 400; }
.field-input { width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; box-sizing: border-box; }
.field-textarea { width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; resize: vertical; box-sizing: border-box; }
.images-row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 8px; }
.img-thumb { width: 64px; height: 64px; border-radius: 8px; overflow: hidden; position: relative; cursor: pointer; border: 1px solid #eee; }
.img-thumb img { width: 100%; height: 100%; object-fit: cover; }
.img-remove { position: absolute; top: -4px; right: -4px; width: 20px; height: 20px; border-radius: 50%; background: #e74c3c; color: #fff; border: none; font-size: 14px; cursor: pointer; line-height: 18px; text-align: center; }
.add-img-btn { width: 64px; height: 64px; border: 2px dashed #ccc; border-radius: 8px; background: #fafafa; font-size: 13px; color: #999; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.btn-block { width: 100%; margin-top: 16px; padding: 12px; font-size: 16px; }
.admin-actions { display: flex; gap: 8px; margin-top: 12px; }
.btn-outline { background: #fff; border: 1px solid #3498db; color: #3498db; }
.timeline { margin-top: 20px; padding-top: 16px; border-top: 1px solid #eee; }
.tl-item { font-size: 13px; color: #666; padding: 4px 0; }
</style>
