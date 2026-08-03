import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const toast = ref('')
  let toastTimer = null

  function showToast(msg, duration = 2000) {
    toast.value = msg
    if (toastTimer) clearTimeout(toastTimer)
    toastTimer = setTimeout(() => { toast.value = '' }, duration)
  }

  return { toast, showToast }
})
