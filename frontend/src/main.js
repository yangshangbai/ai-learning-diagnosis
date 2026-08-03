import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles/variables.css'
import './styles/global.css'
import './styles/components.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.config.errorHandler = (err, instance, info) => {
  console.warn('Vue error:', err.message)

  // Report to backend error log
  try {
    const payload = {
      endpoint: window.location.hash || '/',
      method: 'RENDER',
      error_type: err.name || 'VueError',
      error_message: (err.message || String(err)).slice(0, 500),
      status_code: 0,
      stack_trace: (err.stack || '').slice(0, 500),
      request_body: info || '',
      user_id: null,
      user_name: '',
      source: 'frontend',
    }
    fetch('/api/logs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).catch(() => {})
  } catch {}
}
app.mount('#app')
