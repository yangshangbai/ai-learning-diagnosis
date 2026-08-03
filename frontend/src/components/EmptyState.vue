<template>
  <div class="empty-state">
    <div class="empty-icon" v-if="icon" v-html="icon"></div>
    <div class="empty-icon" v-else>
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--gray-300)" stroke-width="1.5">
        <rect x="3" y="3" width="18" height="18" rx="2"/>
        <path d="M9 9h6M9 13h6M9 17h4"/>
      </svg>
    </div>
    <h3 class="empty-title">{{ title }}</h3>
    <p class="empty-desc" v-if="desc">{{ desc }}</p>
    <button v-if="action" class="btn btn-primary btn-sm" @click="$emit('action')">{{ action }}</button>
  </div>
</template>

<script setup>
defineProps({
  icon: { type: String, default: '' },
  title: { type: String, default: '暂无数据' },
  desc: { type: String, default: '' },
  action: { type: String, default: '' }
})
defineEmits(['action'])
</script>

<style scoped>
.empty-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; padding: 48px 24px; text-align: center;
}
.empty-icon { margin-bottom: 16px; opacity: .6 }
.empty-title { font-size: 16px; font-weight: 600; color: var(--gray-500); margin-bottom: 8px }
.empty-desc { font-size: 13px; color: var(--gray-400); margin-bottom: 20px; max-width: 260px }
</style>
