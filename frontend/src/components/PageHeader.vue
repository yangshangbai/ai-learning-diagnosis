<template>
  <header class="page-header">
    <button v-if="showBack" class="btn-back" @click="goBack">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>
    </button>
    <h1 class="header-title">{{ title }}</h1>
    <div class="header-actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup>
import { useRouter } from 'vue-router'

const props = defineProps({
  title: { type: String, default: '' },
  showBack: { type: Boolean, default: false },
  backPath: { type: String, default: '' }
})

const router = useRouter()

function goBack() {
  if (props.backPath) {
    router.push(props.backPath)
  } else {
    router.back()
  }
}
</script>

<style scoped>
.page-header {
  position: sticky; top: 0; z-index: 100;
  background: #fff; border-bottom: 1px solid var(--gray-200);
  display: flex; align-items: center; padding: 12px 16px;
  min-height: 48px;
}
.btn-back {
  background: none; border: none; cursor: pointer;
  color: var(--gray-700); padding: 4px; margin-right: 8px;
  display: flex; align-items: center; justify-content: center;
}
.header-title {
  flex: 1; font-size: 17px; font-weight: 600; color: var(--gray-900);
}
.header-actions {
  display: flex; align-items: center; gap: 8px;
}
</style>
