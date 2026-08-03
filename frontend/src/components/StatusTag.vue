<template>
  <span class="tag" :class="tagClass">{{ label }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, default: '' },
  type: { type: String, default: 'task' }
})

const label = computed(() => {
  if (props.type === 'task') {
    const map = {
      draft: '草稿', pending_upload: '待上传', ai_processing: 'AI批改中',
      pending_review: '待确认', completed: '已完成', rejected: '驳回',
      partial_confirmed: '部分确认'
    }
    return map[props.status] || props.status
  }
  if (props.type === 'verdict') {
    const map = { correct: '正确', incorrect: '错误', partially_correct: '半对', uncertain: '无法判断' }
    return map[props.status] || props.status
  }
  if (props.type === 'mastery') {
    const map = { mastered: '已掌握', weak: '薄弱', medium: '一般', not_started: '未开始' }
    return map[props.status] || props.status
  }
  return props.status
})

const tagClass = computed(() => {
  if (props.type === 'task') {
    const map = {
      draft: 'tag-gray', pending_upload: 'tag-yellow', ai_processing: 'tag-primary',
      pending_review: 'tag-yellow', completed: 'tag-green', rejected: 'tag-red',
      partial_confirmed: 'tag-yellow'
    }
    return map[props.status] || 'tag-gray'
  }
  if (props.type === 'verdict') {
    const map = { correct: 'tag-green', incorrect: 'tag-red', partially_correct: 'tag-yellow', uncertain: 'tag-gray' }
    return map[props.status] || 'tag-gray'
  }
  if (props.type === 'mastery') {
    const map = { mastered: 'tag-green', weak: 'tag-red', medium: 'tag-yellow', not_started: 'tag-gray' }
    return map[props.status] || 'tag-gray'
  }
  return 'tag-gray'
})
</script>
