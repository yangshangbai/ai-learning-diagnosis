<template>
  <teleport to="body">
    <div v-if="show" class="overlay" @click.self="$emit('close')">
      <div class="bottom-sheet">
        <div class="sheet-handle"></div>
        <h3 class="sheet-title">{{ title }}</h3>
        <div class="sheet-body">
          <slot />
        </div>
        <div class="sheet-footer">
          <button class="btn btn-outline" @click="$emit('close')">取消</button>
          <button class="btn btn-primary" @click="$emit('save')">保存</button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
defineProps({
  show: { type: Boolean, default: false },
  title: { type: String, default: '' }
})
defineEmits(['close', 'save'])
</script>

<style scoped>
.overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,.4);
  z-index: 300; display: flex; align-items: flex-end;
}
.bottom-sheet {
  background: #fff; border-radius: var(--radius) var(--radius) 0 0;
  width: 100%; max-width: 420px; margin: 0 auto;
  max-height: 80vh; display: flex; flex-direction: column;
  animation: slideUp .3s ease;
}
@keyframes slideUp { from { transform: translateY(100%) } to { transform: translateY(0) } }
.sheet-handle {
  width: 36px; height: 4px; background: var(--gray-300);
  border-radius: 2px; margin: 12px auto 8px;
}
.sheet-title {
  font-size: 16px; font-weight: 600; text-align: center; padding: 0 16px 12px;
}
.sheet-body {
  flex: 1; overflow-y: auto; padding: 0 16px;
}
.sheet-footer {
  display: flex; gap: 12px; padding: 16px; border-top: 1px solid var(--gray-200);
}
.sheet-footer .btn { flex: 1 }
</style>
