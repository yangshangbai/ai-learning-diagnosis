<template>
  <div class="load-spinner">
    <div class="spinner"></div>
    <p v-if="text" class="spinner-text">{{ text }}</p>
  </div>
</template>

<script setup>
defineProps({
  text: { type: String, default: '' }
})
</script>

<style scoped>
.load-spinner {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; padding: 32px;
}
.spinner {
  width: 32px; height: 32px; border: 3px solid var(--gray-200);
  border-top-color: var(--primary); border-radius: 50%;
  animation: spin .6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg) } }
.spinner-text { margin-top: 12px; font-size: 13px; color: var(--gray-400) }
</style>
