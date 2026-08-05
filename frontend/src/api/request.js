import axios from 'axios'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
}, (error) => Promise.reject(error))

request.interceptors.response.use((response) => {
  return response.data
}, (error) => {
  const msg = error.response?.data?.detail || error.message || '请求失败'
  if (typeof window !== 'undefined' && window._toast) {
    window._toast(msg)
  }

  // Report error to backend log system (fire-and-forget)
  const reportUrl = '/api/logs'
  const errUrl = error.config?.url || ''
  if (errUrl !== reportUrl && errUrl !== '/logs' && errUrl !== '/api/logs') {
    try {
      // Properly serialize error detail (handle Pydantic validation arrays)
      let errMsg = msg
      if (typeof errMsg === 'object') {
        try { errMsg = JSON.stringify(errMsg).slice(0, 1000) } catch {}
      }
      const payload = {
        endpoint: errUrl,
        method: (error.config?.method || 'GET').toUpperCase(),
        error_type: error.response?.status ? 'HTTP ' + error.response.status : String(error.code || 'NetworkError').substring(0, 100),
        error_message: String(errMsg).substring(0, 1000),
        status_code: error.response?.status || 0,
        stack_trace: (error.stack || '').slice(0, 500),
        request_body: '',
        user_id: null,
        user_name: '',
        source: 'frontend',
      }
      // Only include request_body for non-GET requests
      if (error.config?.data) {
        try {
          payload.request_body = typeof error.config.data === 'string'
            ? error.config.data.slice(0, 500)
            : JSON.stringify(error.config.data).slice(0, 500)
        } catch {}
      }
      // Fire and forget - don't let failure cascade
      fetch('/api/logs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }).catch(() => {})
    } catch {}
  }

  if (error.response?.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    localStorage.removeItem('role')
    window.location.hash = '#/login'
  }
  return Promise.reject(error)
})

export default request
