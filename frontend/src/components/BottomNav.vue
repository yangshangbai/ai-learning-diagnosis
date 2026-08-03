<template>
  <nav class="bottom-nav">
    <button
      v-for="item in items"
      :key="item.key"
      class="nav-item"
      :class="{ active: active === item.key }"
      @click="$emit('nav', item.key)"
    >
      <span class="nav-icon" v-html="item.icon"></span>
      <span class="nav-label">{{ item.label }}</span>
      <span v-if="item.badge" class="badge">{{ item.badge }}</span>
    </button>
  </nav>
</template>

<script setup>
defineProps({
  items: { type: Array, required: true },
  active: { type: String, default: '' }
})
defineEmits(['nav'])
</script>

<style scoped>
.bottom-nav {
  position: fixed; bottom: 0; left: 50%; transform: translateX(-50%);
  width: 100%; max-width: 420px; background: #fff;
  border-top: 1px solid var(--gray-200);
  display: flex; justify-content: space-around;
  padding: 6px 0 calc(6px + var(--safe-bottom));
  z-index: 200;
}
.nav-item {
  display: flex; flex-direction: column; align-items: center;
  gap: 2px; background: none; border: none; cursor: pointer;
  padding: 4px 8px; color: var(--gray-400); font-size: 10px;
  position: relative; min-width: 56px;
}
.nav-item.active { color: var(--primary) }
.nav-icon { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center }
.nav-icon :deep(svg) { width: 22px; height: 22px }
.nav-label { line-height: 1.2 }
.badge {
  position: absolute; top: 0; right: 2px;
  background: var(--danger); color: #fff; font-size: 10px;
  min-width: 16px; height: 16px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  padding: 0 4px;
}
</style>
