import request from './request'

export const studentsAPI = {
  getList: (params) => request.get('/students', { params }),
  getById: (id) => request.get(`/students/${id}`),
  create: (data) => request.post('/students', data),
  update: (id, data) => request.put(`/students/${id}`, data),
  remove: (id) => request.delete(`/students/${id}`),
  saveReport: (id, data) => request.put(`/students/${id}/report`, data),
  getSnapshots: (id) => request.get(`/students/${id}/snapshots`),
  getTasks: (id) => request.get(`/students/${id}/tasks`),
}
