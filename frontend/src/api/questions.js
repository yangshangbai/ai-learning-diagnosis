import request from './request'

export const questionsAPI = {
  getList: (params) => request.get('/questions', { params }),
  getById: (id) => request.get(`/questions/${id}`),
  create: (data) => request.post('/questions', data),
  update: (id, data) => request.put(`/questions/${id}`, data),
  remove: (id) => request.delete(`/questions/${id}`),
}
