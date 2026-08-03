<template>
  <div id="app-root">
    <router-view />
    <div v-if="appStore.toast" class="toast">{{ appStore.toast }}</div>
  </div>
</template>

<script setup>
import { useAppStore } from '@/stores/app'
const appStore = useAppStore()
</script>
