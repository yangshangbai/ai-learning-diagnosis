import request from './request'

export const knowledgeAPI = {
  getTree: (params) => request.get('/knowledge', { params }),
  getFlat: (params) => request.get('/knowledge', { params }),
  getById: (id) => request.get(`/knowledge/${id}`),
  create: (data) => request.post('/knowledge', data),
  update: (id, data) => request.put(`/knowledge/${id}`, data),
  remove: (id) => request.delete(`/knowledge/${id}`),
}
