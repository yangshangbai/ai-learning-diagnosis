export function roleLabel(r) {
  const m = { teacher: '普通老师', admin: '校区管理员', research: '教研管理员', super: '超级管理员' }
  return m[r] || r
}

export function statusLabel(s) {
  const m = {
    draft: '草稿', pending_upload: '待上传学生卷', ai_processing: 'AI批改中',
    pending_review: '待老师确认', completed: '已完成', rejected: '驳回重批',
    partial_confirmed: '部分确认'
  }
  return m[s] || s
}

export function verdictLabel(v) {
  const m = { correct: '正确', incorrect: '错误', partially_correct: '半对', uncertain: '无法判断' }
  return m[v] || v
}

export function verdictIcon(v) {
  const m = { correct: '✓', incorrect: '✗', partially_correct: '◐', uncertain: '?' }
  return m[v] || '?'
}

export function verdictTag(v) {
  const m = { correct: 'tag-green', incorrect: 'tag-red', partially_correct: 'tag-yellow', uncertain: 'tag-gray' }
  return m[v] || 'tag-gray'
}

export function difficultyStars(n) {
  return '★'.repeat(n) + '☆'.repeat(Math.max(0, 3 - n))
}

export function formatDate(dateStr, format = 'YYYY-MM-DD') {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return dateStr
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  if (format === 'YYYY-MM-DD HH:mm') return `${y}-${m}-${day} ${h}:${min}`
  if (format === 'MM-DD') return `${m}-${day}`
  return `${y}-${m}-${day}`
}

export function debounce(fn, delay = 300) {
  let timer = null
  return function (...args) {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => fn.apply(this, args), delay)
  }
}

export function truncate(str, len = 20) {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '...' : str
}
