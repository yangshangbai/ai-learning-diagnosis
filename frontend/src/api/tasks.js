import request from './request'

export const tasksAPI = {
  getList: (params) => request.get('/tasks', { params }),
  getById: (id) => request.get(`/tasks/${id}`),
  create: (data) => request.post('/tasks', data),
  update: (id, data) => request.put(`/tasks/${id}`, data),
  remove: (id) => request.delete(`/tasks/${id}`),
  updateStatus: (id, status) => request.patch(`/tasks/${id}/status`, { status }),
  runAI: (id) => request.post(`/tasks/${id}/run-ai`),
}
