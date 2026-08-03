<template>
  <div class="kpi-card">
    <div class="kpi-label">{{ label }}</div>
    <div class="kpi-value" :style="{ color: color || 'var(--gray-900)' }">{{ value }}</div>
    <div v-if="trend !== undefined && trend !== null" class="kpi-trend" :class="trend >= 0 ? 'trend-up' : 'trend-down'">
      <span>{{ trend >= 0 ? '↑' : '↓' }}</span>
      <span>{{ Math.abs(trend) }}%</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  label: { type: String, default: '' },
  value: { type: [String, Number], default: '' },
  trend: { type: Number, default: null },
  color: { type: String, default: '' }
})
</script>

<style scoped>
.kpi-card {
  background: #fff; border-radius: var(--radius);
  padding: 16px; box-shadow: var(--shadow);
  display: flex; flex-direction: column; gap: 4px;
}
.kpi-label { font-size: 12px; color: var(--gray-500) }
.kpi-value { font-size: 24px; font-weight: 700 }
.kpi-trend { font-size: 12px; display: flex; align-items: center; gap: 2px }
.trend-up { color: var(--success) }
.trend-down { color: var(--danger) }
</style>
