import request from './request'

export const exercisesAPI = {
  getList: (params) => request.get('/exercises', { params }),
  create: (data) => request.post('/exercises', data),
  update: (id, data) => request.put(`/exercises/${id}`, data),
  remove: (id) => request.delete(`/exercises/${id}`),
}
