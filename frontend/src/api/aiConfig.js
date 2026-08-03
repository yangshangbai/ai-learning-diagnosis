import request from './request'

export const aiConfigAPI = {
  getConfig: () => request.get('/admin/ai-config'),
  saveConfig: (configs) => request.put('/admin/ai-config', { configs }),
}
